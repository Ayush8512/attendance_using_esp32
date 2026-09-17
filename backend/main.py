"""
Face Recognition Attendance System — FastAPI + SQLite
=====================================================

A self-contained backend that:
  • Stores student data (roll_no, name, face_encoding) in SQLite.
  • Stores attendance records (roll_no, date, time, status) in SQLite.
  • Exposes POST /register   — register a student with a photo.
  • Exposes POST /verify     — verify a live photo and mark attendance.
  • Exposes POST /end_class  — end a class, generate an Excel attendance
                                report, and email it to the teacher.

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import io
import json
import logging
import os
import smtplib
import tempfile
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

import aiosqlite
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Try loading environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

# Try importing real face_recognition (requires dlib), fallback to PIL-based mock if not installed
try:
    import face_recognition
    USE_REAL_FR = True
except ImportError:
    USE_REAL_FR = False
    import hashlib
    from PIL import Image

logger = logging.getLogger("attendance")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "attendance.db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)
FACE_MATCH_TOLERANCE = 0.50  # 0.50 = strict matching, prevents false approvals

# ---------------------------------------------------------------------------
# SMTP / Email configuration  (override via environment variables or .env)
# ---------------------------------------------------------------------------

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "your_email@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your_app_password")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", SMTP_USER)

# ---------------------------------------------------------------------------
# Timetable mapping & strict attendance window configuration
# ---------------------------------------------------------------------------
# Key  : (weekday_name, hour_24)  — e.g. ("Monday", 9) means 09:00-09:59
# Value: dict with "subject", "teacher_email", "start_minute", and "allowed_window_minutes"
#
# Students can only mark attendance within `allowed_window_minutes` (default 10)
# after class start time.
# ---------------------------------------------------------------------------

ATTENDANCE_WINDOW_MINUTES = 10  # Strict 10-minute allowed attendance window

TIMETABLE: dict[tuple[str, int], dict[str, any]] = {
    # ── Monday ────────────────────────────────────────────────────────────
    ("Monday", 9):  {"subject": "Mathematics",        "teacher_email": "gupta@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Monday", 10): {"subject": "Physics",             "teacher_email": "verma@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Monday", 11): {"subject": "Basic Electronics",   "teacher_email": "sharma@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Monday", 14): {"subject": "Data Structures",     "teacher_email": "singh@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    # ── Tuesday ───────────────────────────────────────────────────────────
    ("Tuesday", 9):  {"subject": "Chemistry",          "teacher_email": "patel@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Tuesday", 10): {"subject": "English",            "teacher_email": "mehta@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Tuesday", 11): {"subject": "Basic Electronics",  "teacher_email": "sharma@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Tuesday", 14): {"subject": "Computer Networks",  "teacher_email": "kumar@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    # ── Wednesday ─────────────────────────────────────────────────────────
    ("Wednesday", 9):  {"subject": "Mathematics",      "teacher_email": "gupta@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Wednesday", 10): {"subject": "Physics",          "teacher_email": "verma@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Wednesday", 11): {"subject": "Digital Logic",    "teacher_email": "rao@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Wednesday", 14): {"subject": "Data Structures",  "teacher_email": "singh@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    # ── Thursday ──────────────────────────────────────────────────────────
    ("Thursday", 9):  {"subject": "Chemistry",         "teacher_email": "patel@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Thursday", 10): {"subject": "English",           "teacher_email": "mehta@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Thursday", 11): {"subject": "Basic Electronics", "teacher_email": "sharma@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Thursday", 14): {"subject": "Computer Networks", "teacher_email": "kumar@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    # ── Friday ────────────────────────────────────────────────────────────
    ("Friday", 9):  {"subject": "Mathematics",         "teacher_email": "gupta@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Friday", 10): {"subject": "Physics Lab",         "teacher_email": "verma@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Friday", 11): {"subject": "Digital Logic",       "teacher_email": "rao@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
    ("Friday", 14): {"subject": "Project Work",        "teacher_email": "singh@college.edu", "start_minute": 0, "allowed_window_minutes": 10},
}


def get_class_info(dt: datetime | None = None) -> dict[str, any] | None:
    """
    Look up the timetable for the given datetime (defaults to *now*).

    Returns ``{"subject": ..., "teacher_email": ..., "start_minute": ..., "allowed_window_minutes": ...}``
    or ``None`` if no class is scheduled for that slot.
    """
    if dt is None:
        dt = datetime.now()
    day_name = dt.strftime("%A")      # e.g. "Monday"
    hour = dt.hour                    # 0-23
    return TIMETABLE.get((day_name, hour))


async def get_class_info_from_db(dt: datetime | None = None) -> dict[str, any] | None:
    """
    Look up the timetable in SQLite database first, falling back to memory.
    """
    if dt is None:
        dt = datetime.now()
    day_name = dt.strftime("%A")
    hour = dt.hour

    try:
        db = await get_db()
        try:
            cursor = await db.execute(
                """
                SELECT day, hour, start_minute, allowed_window_minutes, subject, teacher_email
                FROM timetable
                WHERE day = ? AND hour = ?
                """,
                (day_name, hour),
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
        finally:
            await db.close()
    except Exception as exc:
        logger.debug("Could not query timetable table: %s", exc)

    return get_class_info(dt)


def check_attendance_window(class_info: dict, dt: datetime | None = None) -> tuple[bool, str, str]:
    """
    Strictly validate if the given datetime is within the allowed attendance window.
    Returns (is_allowed, error_detail, window_end_str).
    """
    if dt is None:
        dt = datetime.now()

    start_hour = class_info.get("hour", dt.hour)
    start_minute = class_info.get("start_minute", 0)
    allowed_minutes = class_info.get("allowed_window_minutes", ATTENDANCE_WINDOW_MINUTES)

    class_start = dt.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    window_end = class_start + timedelta(minutes=allowed_minutes)
    window_end_str = window_end.strftime("%I:%M %p")
    start_str = class_start.strftime("%I:%M %p")

    if dt < class_start:
        return False, f"Class has not started yet. Class starts at {start_str}.", window_end_str

    if dt > window_end:
        return (
            False,
            f"Time limit exceeded. Allowed {allowed_minutes}-minute attendance window for {class_info.get('subject', 'class')} ended at {window_end_str}.",
            window_end_str,
        )

    return True, "", window_end_str

# ---------------------------------------------------------------------------
# Excel report generation (pandas)
# ---------------------------------------------------------------------------

async def generate_attendance_excel(
    target_date: str,
    subject: str,
) -> tuple[str, str]:
    """
    Query today's attendance for the specified subject, join with the students table,
    and write a formatted Excel workbook with summary statistics.
    Returns (filepath, filename).
    """
    db = await get_db()
    try:
        # All registered students
        cur_students = await db.execute(
            "SELECT roll_no, name FROM students ORDER BY roll_no"
        )
        all_students = await cur_students.fetchall()

        # Students marked present in THIS subject on target_date
        cur_present = await db.execute(
            "SELECT DISTINCT a.roll_no, a.time FROM attendance a WHERE a.date = ? AND (a.subject = ? OR a.subject LIKE ?)",
            (target_date, subject, f"%{subject}%"),
        )
        present_rows = await cur_present.fetchall()
    finally:
        await db.close()

    present_map = {row["roll_no"]: row["time"] for row in present_rows}

    records = []
    for s in all_students:
        is_pres = s["roll_no"] in present_map
        records.append(
            {
                "Roll No": s["roll_no"],
                "Student Name": s["name"],
                "Subject": subject,
                "Date": target_date,
                "Scan Time": present_map.get(s["roll_no"], "-"),
                "Attendance Status": "Present" if is_pres else "Absent",
            }
        )

    df = pd.DataFrame(records)

    clean_sub = "".join(c for c in subject if c.isalnum() or c in (" ", "_", "-")).strip()
    filename = f"Attendance_{clean_sub.replace(' ', '_')}_{target_date}.xlsx"
    filepath = os.path.join(REPORTS_DIR, filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=f"{clean_sub[:28]}")

    logger.info("Excel report generated → %s", filepath)
    return filepath, filename

# ---------------------------------------------------------------------------
# Email sender (smtplib)
# ---------------------------------------------------------------------------

def send_email_with_attachment(
    to_email: str,
    subject_line: str,
    body: str,
    attachment_path: str,
) -> None:
    """
    Send an email with a single ``.xlsx`` attachment via SMTP (TLS).

    Raises on failure so the caller can surface the error to the client.
    """
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject_line

    msg.attach(MIMEText(body, "plain"))

    # Attach the Excel file
    basename = os.path.basename(attachment_path)
    with open(attachment_path, "rb") as f:
        part = MIMEApplication(f.read(), Name=basename)
    part["Content-Disposition"] = f'attachment; filename="{basename}"'
    msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)

    logger.info("Email sent to %s — subject: %s", to_email, subject_line)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def get_db() -> aiosqlite.Connection:
    """Open (and return) a connection to the SQLite database."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    """Create tables if they do not already exist."""
    db = await get_db()
    try:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                roll_no       TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                face_encoding TEXT NOT NULL,  -- JSON-serialised list of 128 floats
                is_locked     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT,
                updated_at    TEXT
            )
            """
        )
        # Safe column migration for existing DB
        for col in [
            "ALTER TABLE students ADD COLUMN is_locked INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE students ADD COLUMN created_at TEXT",
            "ALTER TABLE students ADD COLUMN updated_at TEXT",
        ]:
            try:
                await db.execute(col)
            except Exception:
                pass

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no TEXT    NOT NULL,
                date    TEXT    NOT NULL,       -- YYYY-MM-DD
                time    TEXT    NOT NULL,       -- HH:MM:SS
                subject TEXT    NOT NULL DEFAULT '',
                status  TEXT    NOT NULL DEFAULT 'Present',
                FOREIGN KEY (roll_no) REFERENCES students(roll_no)
            )
            """
        )
        try:
            await db.execute("ALTER TABLE attendance ADD COLUMN subject TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS timetable (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                day                    TEXT    NOT NULL,
                hour                   INTEGER NOT NULL,
                start_minute           INTEGER NOT NULL DEFAULT 0,
                allowed_window_minutes INTEGER NOT NULL DEFAULT 10,
                subject                TEXT    NOT NULL,
                teacher_email          TEXT    NOT NULL,
                UNIQUE(day, hour)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS system_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        await db.execute(
            "INSERT OR IGNORE INTO system_settings (key, value) VALUES ('registration_open', '1')"
        )

        # Seed timetable table from default entries if empty
        cursor = await db.execute("SELECT COUNT(*) as count FROM timetable")
        row = await cursor.fetchone()
        if row and row["count"] == 0:
            for (day, hour), info in TIMETABLE.items():
                await db.execute(
                    """
                    INSERT OR IGNORE INTO timetable (day, hour, start_minute, allowed_window_minutes, subject, teacher_email)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        day,
                        hour,
                        info.get("start_minute", 0),
                        info.get("allowed_window_minutes", 10),
                        info["subject"],
                        info["teacher_email"],
                    ),
                )
        await db.commit()
    finally:
        await db.close()

# ---------------------------------------------------------------------------
# Face-encoding utilities
# ---------------------------------------------------------------------------

async def extract_face_encoding(file: UploadFile) -> List[float]:
    """Read an uploaded image and return the first 128-d face encoding."""
    contents = await file.read()
    if USE_REAL_FR:
        image = face_recognition.load_image_file(io.BytesIO(contents))
        face_locations = face_recognition.face_locations(image, model="hog")
        if not face_locations:
            raise ValueError("No face detected in photo. Please ensure your face is well-lit, upright, and clearly visible.")
        if len(face_locations) > 1:
            raise ValueError("Multiple faces detected in photo. Please ensure only one person is in the frame.")
        encodings = face_recognition.face_encodings(image, known_face_locations=face_locations, num_jitters=1)
        if not encodings:
            raise ValueError("Could not extract facial features. Please retake photo with clearer lighting.")
        return encodings[0].tolist()
    else:
        raise ValueError("Face recognition engine is not installed on the server. Please ensure dlib/face_recognition is active.")


def match_encoding(
    known_encoding: List[float],
    unknown_encoding: List[float],
    tolerance: float = FACE_MATCH_TOLERANCE,
) -> tuple[bool, float]:
    """Compare two face encodings. Returns (is_match, distance)."""
    known = np.array(known_encoding)
    unknown = np.array(unknown_encoding)
    if USE_REAL_FR:
        distance = float(face_recognition.face_distance([known], unknown)[0])
    else:
        distance = float(np.linalg.norm(known - unknown))
    is_match = distance <= tolerance
    return is_match, distance

# ---------------------------------------------------------------------------
# Application lifespan — initialise the database on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Face Recognition Attendance System",
    version="1.0.0",
    description="Register students with a photo and verify attendance via face recognition.",
    lifespan=lifespan,
)

# Allow requests from any origin (useful for mobile / web front-ends).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "face_engine": "Real (dlib 128-d ResNet)" if USE_REAL_FR else "Unavailable",
        "message": "Face Recognition Attendance System API is running.",
    }


@app.post("/register")
async def register_student(
    roll_no: str = Form(..., description="Unique roll number of the student"),
    name: str = Form(..., description="Full name of the student"),
    photo: UploadFile = File(..., description="A clear face photo of the student"),
):
    """
    Register a new student or update existing profile if unlocked by Admin.
    Extracts the 128-dimensional face encoding and locks the biometric profile.
    """
    clean_roll = roll_no.strip().upper()
    clean_name = name.strip()

    # --- Check Admin Registration Open setting ---
    db = await get_db()
    try:
        setting_cur = await db.execute(
            "SELECT value FROM system_settings WHERE key = 'registration_open'"
        )
        srow = await setting_cur.fetchone()
        if srow and srow["value"] == "0":
            raise HTTPException(
                status_code=403,
                detail="Student registration is currently CLOSED by College Administrator.",
            )

        # Check for existing student
        cursor = await db.execute(
            "SELECT roll_no, name, is_locked FROM students WHERE roll_no = ?", (clean_roll,)
        )
        existing = await cursor.fetchone()

        # Security Protection: If student already exists and is locked, block re-registration
        if existing and (existing["is_locked"] is None or existing["is_locked"] == 1):
            raise HTTPException(
                status_code=403,
                detail=f"Roll Number '{clean_roll}' is already locked with a registered biometric profile. Re-registration is blocked for security. Please ask your Teacher/Admin from dashboard to unlock your biometrics.",
            )

        # --- Validate image & extract encoding ---
        try:
            encoding = await extract_face_encoding(photo)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        encoding_json = json.dumps(encoding)
        now_iso = datetime.now().isoformat()

        if existing:
            # Re-enroll student (previously unlocked by admin) and lock
            await db.execute(
                "UPDATE students SET name = ?, face_encoding = ?, is_locked = 1, updated_at = ? WHERE roll_no = ?",
                (clean_name, encoding_json, now_iso, clean_roll),
            )
            await db.commit()
            return {
                "status": "success",
                "is_update": True,
                "message": f"Biometric profile for '{clean_name}' (Roll No: {clean_roll}) updated and locked successfully.",
            }

        # New registration: Insert and lock permanently
        await db.execute(
            "INSERT INTO students (roll_no, name, face_encoding, is_locked, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
            (clean_roll, clean_name, encoding_json, now_iso, now_iso),
        )
        await db.commit()
    finally:
        await db.close()

    return {
        "status": "success",
        "is_update": False,
        "message": f"Student '{clean_name}' (Roll No: {clean_roll}) enrolled and locked successfully.",
    }


@app.post("/verify")
async def verify_attendance(
    photo: UploadFile = File(..., description="A live photo captured from the mobile app"),
    roll_no: str | None = Form(None, description="Optional Roll Number for direct 1-to-1 biometric matching"),
):
    """
    Verify a student's identity and mark attendance.
    Supports direct 1-to-1 student matching (anti-proxy) and 1-to-many fallback.
    """
    # ── 1. Strict Time Window Check (Server Time) ──
    now = datetime.now()
    class_info = await get_class_info_from_db(now)

    if not class_info:
        raise HTTPException(
            status_code=403,
            detail=f"Time limit exceeded. No scheduled class found for current time ({now.strftime('%A %I:%M %p')}).",
        )

    is_allowed, time_err, window_end_str = check_attendance_window(class_info, now)
    if not is_allowed:
        raise HTTPException(
            status_code=403,
            detail=time_err,
        )

    # ── 2. Extract encoding from the live photo ──
    try:
        unknown_encoding = await extract_face_encoding(photo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    current_subject = class_info.get("subject", "Class")

    # --- Load students for matching ---
    db = await get_db()
    try:
        if roll_no and roll_no.strip():
            # ── 1-to-1 Direct Identity Verification (Anti-Proxy Architecture) ──
            clean_roll = roll_no.strip().upper()
            cursor = await db.execute(
                "SELECT roll_no, name, face_encoding FROM students WHERE roll_no = ?",
                (clean_roll,),
            )
            student = await cursor.fetchone()
            if not student:
                raise HTTPException(
                    status_code=404,
                    detail=f"Student with Roll Number '{clean_roll}' is not enrolled on this server.",
                )

            known_encoding = json.loads(student["face_encoding"])
            is_match, distance = match_encoding(known_encoding, unknown_encoding)
            logger.info(
                "1-to-1 Verification: roll=%s, name=%s, distance=%.4f (threshold=%.2f)",
                clean_roll,
                student["name"],
                distance,
                FACE_MATCH_TOLERANCE,
            )

            if not is_match:
                raise HTTPException(
                    status_code=403,
                    detail=f"Face mismatch! Live face (Distance: {distance:.2f}) does not match registered biometrics for {student['name']} ({clean_roll}). Proxy attendance strictly rejected.",
                )

            matched_roll_no = student["roll_no"]
            matched_name = student["name"]
        else:
            # ── 1-to-Many General Verification ──
            cursor = await db.execute("SELECT roll_no, name, face_encoding FROM students")
            students = await cursor.fetchall()
            if not students:
                raise HTTPException(
                    status_code=404,
                    detail="No students are registered yet. Please register first.",
                )

            best_match_roll_no: str | None = None
            best_match_name: str | None = None
            best_distance: float = float("inf")

            for student in students:
                known_encoding = json.loads(student["face_encoding"])
                is_match, distance = match_encoding(known_encoding, unknown_encoding)
                if is_match and distance < best_distance:
                    best_distance = distance
                    best_match_roll_no = student["roll_no"]
                    best_match_name = student["name"]

            if best_match_roll_no is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Face did not match any registered student (Lowest distance: {best_distance:.2f} > tolerance {FACE_MATCH_TOLERANCE:.2f}). Only registered students can mark attendance.",
                )

            matched_roll_no = best_match_roll_no
            matched_name = best_match_name

        # --- Prevent duplicate attendance for the same student in THIS subject on today ---
        today = date.today().isoformat()
        dup_cursor = await db.execute(
            "SELECT id FROM attendance WHERE roll_no = ? AND date = ? AND subject = ?",
            (matched_roll_no, today, current_subject),
        )
        duplicate = await dup_cursor.fetchone()
        if duplicate:
            return {
                "status": "already_marked",
                "message": f"Attendance for '{matched_name}' ({matched_roll_no}) is already marked for {current_subject} today.",
                "roll_no": matched_roll_no,
                "name": matched_name,
                "subject": current_subject,
            }

        # --- Mark attendance ---
        now_time_str = now.strftime("%H:%M:%S")
        await db.execute(
            "INSERT INTO attendance (roll_no, date, time, subject, status) VALUES (?, ?, ?, ?, ?)",
            (matched_roll_no, today, now_time_str, current_subject, "Present"),
        )
        await db.commit()
    finally:
        await db.close()

    return {
        "status": "success",
        "message": f"Attendance marked for '{matched_name}' (Roll No: {matched_roll_no}) in {current_subject}.",
        "roll_no": matched_roll_no,
        "name": matched_name,
        "subject": current_subject,
        "date": today,
        "time": now_time_str,
    }


@app.get("/attendance")
async def get_attendance(
    roll_no: str | None = None,
    date_filter: str | None = None,
    subject_filter: str | None = None,
):
    """
    Retrieve attendance records, optionally filtered by `roll_no`, `date_filter` (YYYY-MM-DD), and/or `subject_filter`.
    """
    db = await get_db()
    try:
        query = "SELECT a.roll_no, s.name, a.date, a.time, a.subject, a.status FROM attendance a JOIN students s ON a.roll_no = s.roll_no WHERE 1=1"
        params: list = []

        if roll_no:
            query += " AND a.roll_no = ?"
            params.append(roll_no)
        if date_filter:
            query += " AND a.date = ?"
            params.append(date_filter)
        if subject_filter:
            query += " AND (a.subject = ? OR a.subject LIKE ?)"
            params.extend([subject_filter, f"%{subject_filter}%"])

        query += " ORDER BY a.date DESC, a.time DESC"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
    finally:
        await db.close()

    records = [
        {
            "roll_no": row["roll_no"],
            "name": row["name"],
            "date": row["date"],
            "time": row["time"],
            "subject": row["subject"] or "",
            "status": row["status"],
        }
        for row in rows
    ]

    return {"status": "success", "count": len(records), "records": records}


@app.get("/students")
async def list_students():
    """List all registered students with biometric lock status."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT roll_no, name, is_locked, created_at, updated_at FROM students ORDER BY roll_no")
        rows = await cursor.fetchall()
    finally:
        await db.close()

    students = [
        {
            "roll_no": row["roll_no"],
            "name": row["name"],
            "is_locked": bool(row["is_locked"]) if row["is_locked"] is not None else True,
            "created_at": row["created_at"] or "",
            "updated_at": row["updated_at"] or "",
        }
        for row in rows
    ]
    return {"status": "success", "count": len(students), "students": students}


@app.post("/admin/students/{roll_no}/unlock")
async def unlock_student_biometrics(roll_no: str):
    """Admin unlocks student biometrics allowing them to re-register/update their face photo."""
    clean_roll = roll_no.strip().upper()
    db = await get_db()
    try:
        cur = await db.execute("UPDATE students SET is_locked = 0 WHERE roll_no = ?", (clean_roll,))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Student with roll number '{clean_roll}' not found.")
    finally:
        await db.close()
    return {"status": "success", "message": f"Biometrics for student '{clean_roll}' unlocked. Student can now re-register face photo."}


@app.post("/admin/students/{roll_no}/lock")
async def lock_student_biometrics(roll_no: str):
    """Admin locks student biometrics to prevent re-registration."""
    clean_roll = roll_no.strip().upper()
    db = await get_db()
    try:
        cur = await db.execute("UPDATE students SET is_locked = 1 WHERE roll_no = ?", (clean_roll,))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Student with roll number '{clean_roll}' not found.")
    finally:
        await db.close()
    return {"status": "success", "message": f"Biometrics for student '{clean_roll}' locked."}


@app.get("/admin/settings")
async def get_admin_settings():
    """Retrieve institution admin settings (registration window toggle)."""
    db = await get_db()
    try:
        cur = await db.execute("SELECT key, value FROM system_settings")
        rows = await cur.fetchall()
    finally:
        await db.close()
    settings = {row["key"]: row["value"] for row in rows}
    return {
        "status": "success",
        "registration_open": settings.get("registration_open", "1") == "1",
    }


@app.post("/admin/settings/registration")
async def toggle_registration_setting(data: dict):
    """Toggle registration open / closed for the institution."""
    is_open = "1" if data.get("open", True) else "0"
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO system_settings (key, value) VALUES ('registration_open', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (is_open, is_open),
        )
        await db.commit()
    finally:
        await db.close()
    status_str = "OPEN" if is_open == "1" else "CLOSED"
    return {"status": "success", "message": f"Student registration is now {status_str}.", "registration_open": is_open == "1"}


@app.get("/students/{roll_no}")
async def get_student_profile(roll_no: str):
    """Fetch student profile by roll number to restore local session after app reinstall."""
    clean_roll = roll_no.strip().upper()
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT roll_no, name FROM students WHERE roll_no = ?", (clean_roll,)
        )
        student = await cursor.fetchone()
        if not student:
            raise HTTPException(
                status_code=404,
                detail=f"No registered student found with Roll Number '{clean_roll}'.",
            )
        return {
            "status": "success",
            "roll_no": student["roll_no"],
            "name": student["name"],
        }
    finally:
        await db.close()


@app.delete("/students/{roll_no}")
async def delete_student(roll_no: str):
    """Delete a registered student and their attendance records."""
    db = await get_db()
    try:
        cur = await db.execute("DELETE FROM students WHERE roll_no = ?", (roll_no,))
        await db.execute("DELETE FROM attendance WHERE roll_no = ?", (roll_no,))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Student with roll number '{roll_no}' not found.")
    finally:
        await db.close()
    return {"status": "success", "message": f"Student '{roll_no}' deleted successfully."}



# ---------------------------------------------------------------------------
# End-of-class reporting
# ---------------------------------------------------------------------------

@app.post("/end_class")
async def end_class(
    subject: str | None = Form(None, description="Override subject name (auto-detected from timetable if omitted)"),
    teacher_email: str | None = Form(None, description="Override teacher email (auto-detected from timetable if omitted)"),
):
    """
    Trigger the end-of-class workflow:

    1. **Resolve the class** — uses the current time to look up the timetable,
       or accepts manual ``subject`` / ``teacher_email`` overrides.
    2. **Generate an Excel report** — queries today's attendance from SQLite,
       marks every registered student as Present or Absent, and writes an
       ``.xlsx`` file using pandas.
    3. **Email the report** — sends the workbook as an attachment to the
       teacher via SMTP (runs in a FastAPI ``BackgroundTask`` so the response
       returns immediately).
    """
    now = datetime.now()
    today = date.today().isoformat()

    # --- Resolve class info from timetable or form overrides ---
    class_info = await get_class_info_from_db(now)

    resolved_subject = (subject and subject.strip()) or (class_info["subject"] if class_info else None)
    resolved_email = (teacher_email and teacher_email.strip()) or (class_info["teacher_email"] if class_info else None)

    if not resolved_subject or not resolved_email:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not automatically resolve class. "
                "Please provide 'subject' and 'teacher_email' manually."
            ),
        )

    # --- Generate the Excel attendance report ---
    try:
        excel_path, filename = await generate_attendance_excel(today, resolved_subject)
    except Exception as exc:
        logger.exception("Failed to generate Excel report")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating attendance report: {exc}",
        )

    download_url = f"/reports/{filename}"
    email_sent = False
    email_error = None

    # Check if SMTP credentials are configured (not default placeholders)
    if SMTP_USER and SMTP_USER != "your_email@gmail.com" and SMTP_PASSWORD and SMTP_PASSWORD != "your_app_password":
        try:
            send_email_with_attachment(
                to_email=resolved_email,
                subject_line=f"Attendance Report — {resolved_subject} — {today}",
                body=(
                    f"Dear Professor,\n\n"
                    f"Please find attached the attendance report for "
                    f"'{resolved_subject}' held on {today}.\n\n"
                    f"This report was auto-generated by the Face Recognition "
                    f"Attendance System.\n\n"
                    f"Regards,\n"
                    f"Smart Attendance Bot"
                ),
                attachment_path=excel_path,
            )
            email_sent = True
        except Exception as exc:
            logger.warning("SMTP email delivery to %s failed: %s", resolved_email, exc)
            email_error = str(exc)
    else:
        email_error = "SMTP credentials not configured in .env (add SMTP_USER and SMTP_PASSWORD to send emails)."

    if email_sent:
        msg = f"Attendance report for '{resolved_subject}' generated & emailed to {resolved_email}."
    else:
        msg = f"Excel attendance report generated! (Email skipped: {email_error}). Downloading sheet..."

    return {
        "status": "success" if email_sent else "excel_ready",
        "message": msg,
        "subject": resolved_subject,
        "teacher_email": resolved_email,
        "download_url": download_url,
        "filename": filename,
        "email_sent": email_sent,
        "email_error": email_error,
        "date": today,
    }


@app.get("/reports/{filename}")
async def download_report(filename: str):
    """Download a generated Excel attendance sheet."""
    safe_name = os.path.basename(filename)
    file_path = os.path.join(REPORTS_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Attendance report file not found.")
    return FileResponse(
        file_path,
        filename=safe_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/timetable")
async def view_timetable():
    """Return the full timetable with strict attendance windows and current class status."""
    now = datetime.now()
    current_class = await get_class_info_from_db(now)

    window_status = None
    if current_class:
        is_allowed, reason, window_end_str = check_attendance_window(current_class, now)
        window_status = {
            "is_open": is_allowed,
            "window_end": window_end_str,
            "message": "Window open for attendance" if is_allowed else reason,
        }

    schedule = []
    try:
        db = await get_db()
        try:
            cursor = await db.execute(
                """
                SELECT id, day, hour, start_minute, allowed_window_minutes, subject, teacher_email
                FROM timetable
                ORDER BY
                    CASE day
                        WHEN 'Monday' THEN 1
                        WHEN 'Tuesday' THEN 2
                        WHEN 'Wednesday' THEN 3
                        WHEN 'Thursday' THEN 4
                        WHEN 'Friday' THEN 5
                        WHEN 'Saturday' THEN 6
                        WHEN 'Sunday' THEN 7
                        ELSE 8
                    END,
                    hour ASC,
                    start_minute ASC
                """
            )
            rows = await cursor.fetchall()
            for r in rows:
                h = r["hour"]
                sm = r["start_minute"]
                wm = r["allowed_window_minutes"]
                we_h = h + (sm + wm) // 60
                we_m = (sm + wm) % 60
                schedule.append({
                    "id": r["id"],
                    "day": r["day"],
                    "hour": h,
                    "start_minute": sm,
                    "allowed_window_minutes": wm,
                    "time_label": f"{h:02d}:{sm:02d} – {h:02d}:59",
                    "attendance_window": f"{h:02d}:{sm:02d} – {we_h:02d}:{we_m:02d} ({wm} min window)",
                    "subject": r["subject"],
                    "teacher_email": r["teacher_email"],
                })
        finally:
            await db.close()
    except Exception as exc:
        logger.warning("Error loading timetable from DB: %s", exc)

    if not schedule:
        schedule = [
            {
                "id": None,
                "day": day,
                "hour": hour,
                "start_minute": info.get("start_minute", 0),
                "allowed_window_minutes": info.get("allowed_window_minutes", ATTENDANCE_WINDOW_MINUTES),
                "time_label": f"{hour:02d}:{info.get('start_minute', 0):02d} – {hour:02d}:59",
                "attendance_window": f"{hour:02d}:{info.get('start_minute', 0):02d} – {hour:02d}:{info.get('start_minute', 0) + info.get('allowed_window_minutes', ATTENDANCE_WINDOW_MINUTES):02d} ({info.get('allowed_window_minutes', ATTENDANCE_WINDOW_MINUTES)} min window)",
                "subject": info["subject"],
                "teacher_email": info["teacher_email"],
            }
            for (day, hour), info in sorted(
                TIMETABLE.items(),
                key=lambda item: (
                    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"].index(item[0][0]),
                    item[0][1],
                ),
            )
        ]

    return {
        "status": "success",
        "current_slot": {
            "day": now.strftime("%A"),
            "hour": now.hour,
            "time": now.strftime("%H:%M:%S"),
            "class": current_class,
            "window_status": window_status,
        },
        "timetable": schedule,
    }


@app.post("/timetable")
async def add_timetable_entry(
    day: str = Form(..., description="Day of week (e.g. Monday, Tuesday)"),
    hour: int = Form(..., ge=0, le=23, description="Class start hour (0-23)"),
    start_minute: int = Form(0, ge=0, le=59, description="Start minute (0-59, default 0)"),
    allowed_window_minutes: int = Form(10, ge=1, le=60, description="Allowed attendance window in minutes (default 10)"),
    subject: str = Form(..., description="Subject name"),
    teacher_email: str = Form(..., description="Teacher email address"),
):
    """Add or update a class in the timetable with strict allowed attendance window."""
    clean_day = day.strip().capitalize()
    clean_subject = subject.strip()
    clean_email = teacher_email.strip()

    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO timetable (day, hour, start_minute, allowed_window_minutes, subject, teacher_email)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(day, hour) DO UPDATE SET
                start_minute = excluded.start_minute,
                allowed_window_minutes = excluded.allowed_window_minutes,
                subject = excluded.subject,
                teacher_email = excluded.teacher_email
            """,
            (clean_day, hour, start_minute, allowed_window_minutes, clean_subject, clean_email),
        )
        await db.commit()

        # Keep memory cache updated
        TIMETABLE[(clean_day, hour)] = {
            "subject": clean_subject,
            "teacher_email": clean_email,
            "start_minute": start_minute,
            "allowed_window_minutes": allowed_window_minutes,
        }
    finally:
        await db.close()

    return {
        "status": "success",
        "message": f"Class '{clean_subject}' on {clean_day} at {hour:02d}:{start_minute:02d} ({allowed_window_minutes}-min window) saved successfully.",
    }


@app.delete("/timetable/{item_id}")
async def delete_timetable_entry(item_id: int):
    """Delete a class from the timetable."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT day, hour, subject FROM timetable WHERE id = ?", (item_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Timetable entry not found.")

        day, hour, subject = row["day"], row["hour"], row["subject"]
        await db.execute("DELETE FROM timetable WHERE id = ?", (item_id,))
        await db.commit()

        if (day, hour) in TIMETABLE:
            del TIMETABLE[(day, hour)]
    finally:
        await db.close()

    return {
        "status": "success",
        "message": f"Class '{subject}' deleted from timetable.",
    }


# ---------------------------------------------------------------------------
# Frontend Static Files Mount
# ---------------------------------------------------------------------------
# Serve frontend directly so opening http://localhost:8000 loads the full Web Dashboard
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSSIBLE_FRONTEND_PATHS = [
    os.path.join(os.path.dirname(BASE_DIR), "frontend"),
    os.path.join(BASE_DIR, "frontend"),
    r"D:\RFID\frontend",
]

for fpath in POSSIBLE_FRONTEND_PATHS:
    if os.path.isdir(fpath) and os.path.isfile(os.path.join(fpath, "index.html")):
        app.mount("/", StaticFiles(directory=fpath, html=True), name="frontend")
        break


