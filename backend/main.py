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

from PIL import Image, ImageOps

# Try importing real face_recognition (requires dlib), fallback to PIL-based mock if not installed
try:
    import face_recognition
    USE_REAL_FR = True
except ImportError:
    USE_REAL_FR = False
    import hashlib

logger = logging.getLogger("attendance")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "attendance.db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)
FACE_MATCH_TOLERANCE = 0.44  # 0.44 = strict anti-proxy tolerance (blocks re-photographed screens & lookalikes)

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

# ---------------------------------------------------------------------------
# College Branch & Section Configuration (IERT Prayagraj 7 Branches & 4 Years)
# ---------------------------------------------------------------------------

BRANCH_METADATA: dict[str, dict[str, str]] = {
    "A": {"name": "Computer Science & Engineering", "short": "CSE"},
    "B": {"name": "Electronics Engineering", "short": "ECE"},
    "C": {"name": "Industrial & Production Engineering", "short": "IPE"},
    "D": {"name": "Mechanical Engineering", "short": "ME"},
    "E": {"name": "Instrumentation & Control Engineering", "short": "ICE"},
    "F": {"name": "Electrical Engineering", "short": "EE"},
    "G": {"name": "Civil Engineering", "short": "CE"},
}

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


def get_year_label(yr: int | None = None, sec: str | None = None) -> str:
    """Helper to convert year number or section code into standard label (e.g. 1st Year)."""
    if yr and yr in (1, 2, 3, 4):
        suffixes = {1: "1st Year", 2: "2nd Year", 3: "3rd Year", 4: "4th Year"}
        return suffixes.get(yr, f"Year {yr}")
    if sec and len(sec) >= 2 and sec[1] in ("1", "2", "3", "4"):
        y = int(sec[1])
        suffixes = {1: "1st Year", 2: "2nd Year", 3: "3rd Year", 4: "4th Year"}
        return suffixes.get(y, f"Year {y}")
    return "N/A"


async def get_class_info_from_db(
    dt: datetime | None = None,
    section: str | None = None,
    branch_code: str | None = None,
    year: int | None = None,
) -> dict[str, any] | None:
    """
    Look up the timetable in SQLite database first.
    Matches specific section or branch/year if provided, falling back to general class or memory.
    """
    if dt is None:
        dt = datetime.now()
    day_name = dt.strftime("%A")
    hour = dt.hour

    try:
        db = await get_db()
        try:
            current_minute = dt.minute
            # current time in minutes since midnight for range comparison
            current_total = hour * 60 + current_minute

            # Helper SQL: a class is "active" if:
            #   - It starts at current hour (hour = ?) OR
            #   - It has an end_hour that covers current time (hour < ? AND end_hour >= ?)
            # We calculate this with: start_total <= current_total <= end_total
            # For simplicity in SQLite: 
            #   start_total = hour*60 + start_minute
            #   end_total = COALESCE(end_hour, hour)*60 + COALESCE(end_minute, start_minute + allowed_window_minutes)

            def active_where():
                return """
                    (hour * 60 + COALESCE(start_minute, 0)) <= ?
                    AND (
                        CASE
                            WHEN end_hour IS NOT NULL AND end_minute IS NOT NULL
                            THEN end_hour * 60 + end_minute
                            ELSE hour * 60 + COALESCE(start_minute, 0) + COALESCE(allowed_window_minutes, 15)
                        END
                    ) > ?
                """

            # 1. Try to match specific section
            if section:
                cur = await db.execute(
                    f"""
                    SELECT day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email, 
                           COALESCE(section, '') as section, COALESCE(branch_code, '') as branch_code, 
                           COALESCE(branch_name, '') as branch_name, COALESCE(year, 0) as year
                    FROM timetable
                    WHERE day = ? AND {active_where()} AND section = ?
                    ORDER BY hour DESC, start_minute DESC
                    LIMIT 1
                    """,
                    (day_name, current_total, current_total, section.strip().upper()),
                )
                row = await cur.fetchone()
                if row:
                    return dict(row)

            # 2. Try to match branch + year
            if branch_code and year:
                cur = await db.execute(
                    f"""
                    SELECT day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email,
                           COALESCE(section, '') as section, COALESCE(branch_code, '') as branch_code, 
                           COALESCE(branch_name, '') as branch_name, COALESCE(year, 0) as year
                    FROM timetable
                    WHERE day = ? AND {active_where()} AND branch_code = ? AND year = ?
                    ORDER BY hour DESC, start_minute DESC
                    LIMIT 1
                    """,
                    (day_name, current_total, current_total, branch_code.strip().upper(), year),
                )
                row = await cur.fetchone()
                if row:
                    return dict(row)

            # 3. Fallback to general slot (all sections / common class) for this day & time range
            cursor = await db.execute(
                f"""
                SELECT day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email,
                       COALESCE(section, '') as section, COALESCE(branch_code, '') as branch_code, 
                       COALESCE(branch_name, '') as branch_name, COALESCE(year, 0) as year
                FROM timetable
                WHERE day = ? AND {active_where()}
                  AND (section IS NULL OR section = '' OR section = 'All Sections')
                  AND (branch_code IS NULL OR branch_code = '' OR branch_code = 'All Branches')
                ORDER BY hour DESC, start_minute DESC
                LIMIT 1
                """,
                (day_name, current_total, current_total),
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
    end_hour = class_info.get("end_hour")
    end_minute = class_info.get("end_minute")
    allowed_minutes = class_info.get("allowed_window_minutes", ATTENDANCE_WINDOW_MINUTES)

    class_start = dt.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    
    # If end time is provided in the timetable, use it. Otherwise fallback to allowed_window_minutes
    if end_hour is not None and end_minute is not None:
        # Check if class crosses midnight (unlikely but possible)
        window_end = dt.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        if window_end < class_start:
            window_end += timedelta(days=1)
    else:
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
# Excel report generation (pandas & openpyxl)
# ---------------------------------------------------------------------------

async def generate_attendance_excel(
    target_date: str,
    subject: str,
    section: str | None = None,
    branch: str | None = None,
    year: int | None = None,
) -> tuple[str, str]:
    """
    Query today's attendance for the specified subject, join with master roster / registered students,
    and write a formatted Excel workbook with Year, Branch, Section, Class Roll, and AKTU Roll.
    Returns (filepath, filename).
    """
    clean_sec = section.strip().upper() if section else ""
    clean_branch = branch.strip().upper() if branch else ""

    db = await get_db()
    try:
        # 1. Fetch students (Prioritize college_roster if available to get entire enrolled class)
        q_roster = """
            SELECT r.year, r.branch_code, r.branch_name, r.section, r.class_roll_no, r.primary_roll_no as roll_no, r.name,
                   (s.roll_no IS NOT NULL) as is_enrolled_biometrics
            FROM college_roster r
            LEFT JOIN students s ON r.primary_roll_no = s.roll_no
            WHERE 1=1
        """
        params_roster = []
        if clean_sec:
            q_roster += " AND r.section = ?"
            params_roster.append(clean_sec)
        elif clean_branch:
            q_roster += " AND r.branch_code = ?"
            params_roster.append(clean_branch)
        if year:
            q_roster += " AND r.year = ?"
            params_roster.append(year)

        q_roster += " ORDER BY r.section, CAST(r.class_roll_no AS INTEGER), r.primary_roll_no"
        cur_roster = await db.execute(q_roster, params_roster)
        roster_students = await cur_roster.fetchall()

        # If roster returned students, use it; otherwise fallback to registered students table
        if roster_students:
            student_list = [dict(r) for r in roster_students]
        else:
            q_stu = "SELECT roll_no, name, branch_code, branch_name, section, year, class_roll_no, 1 as is_enrolled_biometrics FROM students WHERE 1=1"
            params_stu = []
            if clean_sec:
                q_stu += " AND section = ?"
                params_stu.append(clean_sec)
            elif clean_branch:
                q_stu += " AND branch_code = ?"
                params_stu.append(clean_branch)
            if year:
                q_stu += " AND year = ?"
                params_stu.append(year)
            q_stu += " ORDER BY section, CAST(class_roll_no AS INTEGER), roll_no"
            cur_students = await db.execute(q_stu, params_stu)
            student_list = [dict(r) for r in await cur_students.fetchall()]

        # 2. Query attendance marked present in THIS subject on target_date
        cur_present = await db.execute(
            """
            SELECT DISTINCT a.roll_no, a.time, a.section, a.branch_code 
            FROM attendance a 
            WHERE a.date = ? AND (a.subject = ? OR a.subject LIKE ?)
            """,
            (target_date, subject, f"%{subject}%"),
        )
        present_rows = await cur_present.fetchall()
    finally:
        await db.close()

    present_map = {row["roll_no"]: row["time"] for row in present_rows}

    records = []
    present_count = 0
    absent_count = 0

    for idx, s in enumerate(student_list, start=1):
        is_pres = s["roll_no"] in present_map
        if is_pres:
            present_count += 1
        else:
            absent_count += 1

        b_code = s.get("branch_code") or clean_branch or ""
        b_name = s.get("branch_name") or BRANCH_METADATA.get(b_code, {}).get("name", "")
        sec = s.get("section") or clean_sec or "-"
        y_val = s.get("year") or year or (int(sec[1]) if len(sec) >= 2 and sec[1].isdigit() else 1)
        year_label = get_year_label(y_val, sec)

        records.append(
            {
                "S.No": idx,
                "Class Roll No": s.get("class_roll_no") or "-",
                "Primary / AKTU Roll No": s["roll_no"],
                "Student Name": s["name"],
                "Academic Year": year_label,
                "Branch": f"{b_code} - {b_name}" if b_code else "-",
                "Section": sec,
                "Subject": subject,
                "Date": target_date,
                "Scan Time": present_map.get(s["roll_no"], "-"),
                "Biometrics Registered": "Yes" if s.get("is_enrolled_biometrics") else "Pending",
                "Attendance Status": "Present" if is_pres else "Absent",
            }
        )

    df = pd.DataFrame(records)

    clean_sub = "".join(c for c in subject if c.isalnum() or c in (" ", "_", "-")).strip()
    sec_prefix = f"_{clean_sec}" if clean_sec else ""
    yr_prefix = f"_{get_year_label(year, clean_sec).replace(' ', '_')}" if (year or clean_sec) else ""
    filename = f"Attendance_{clean_sub.replace(' ', '_')}{yr_prefix}{sec_prefix}_{target_date}.xlsx"
    filepath = os.path.join(REPORTS_DIR, filename)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance Sheet")

    logger.info("Excel report generated with Year & Branch metadata → %s (Total: %d, Present: %d, Absent: %d)", filepath, len(records), present_count, absent_count)
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
            "ALTER TABLE students ADD COLUMN device_id TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN branch_code TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN branch_name TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN section TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN year INTEGER DEFAULT 1",
            "ALTER TABLE students ADD COLUMN class_roll_no TEXT DEFAULT ''",
        ]:
            try:
                await db.execute(col)
            except Exception:
                pass

        # College Master Roster table (All 7 Branches & 4 Years)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS college_roster (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                year            INTEGER NOT NULL,
                branch_code     TEXT NOT NULL,
                branch_name     TEXT NOT NULL,
                section         TEXT NOT NULL,
                semester        TEXT NOT NULL,
                class_roll_no   TEXT NOT NULL,
                primary_roll_no TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no     TEXT    NOT NULL,
                date        TEXT    NOT NULL,       -- YYYY-MM-DD
                time        TEXT    NOT NULL,       -- HH:MM:SS
                subject     TEXT    NOT NULL DEFAULT '',
                status      TEXT    NOT NULL DEFAULT 'Present',
                section     TEXT    NOT NULL DEFAULT '',
                branch_code TEXT    NOT NULL DEFAULT '',
                FOREIGN KEY (roll_no) REFERENCES students(roll_no)
            )
            """
        )
        for col in [
            "ALTER TABLE attendance ADD COLUMN subject TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE attendance ADD COLUMN section TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE attendance ADD COLUMN branch_code TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE attendance ADD COLUMN year INTEGER DEFAULT 0",
            "ALTER TABLE timetable ADD COLUMN section TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE timetable ADD COLUMN branch_code TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE timetable ADD COLUMN branch_name TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE timetable ADD COLUMN year INTEGER DEFAULT 0",
            "ALTER TABLE timetable ADD COLUMN end_hour INTEGER",
            "ALTER TABLE timetable ADD COLUMN end_minute INTEGER",
        ]:
            try:
                await db.execute(col)
            except Exception:
                pass

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS timetable (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                day                    TEXT    NOT NULL,
                hour                   INTEGER NOT NULL,
                start_minute           INTEGER NOT NULL DEFAULT 0,
                end_hour               INTEGER,
                end_minute             INTEGER,
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
# Face-encoding utilities & EXIF-Aware Robust Detection
# ---------------------------------------------------------------------------

def load_and_orient_image(contents: bytes) -> np.ndarray:
    """
    Load an image from bytes, apply EXIF auto-transpose (fixes portrait mobile camera orientation),
    downscale large images to max 800x800 for FAST processing, ensure RGB format, 
    and convert to numpy array for dlib/face_recognition.
    """
    pil_img = Image.open(io.BytesIO(contents))
    # Correct EXIF rotation metadata (crucial for portrait selfies taken on mobile phones)
    pil_img = ImageOps.exif_transpose(pil_img)
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    
    # Compress/Resize image to a manageable size to prevent massive CPU slowdowns
    pil_img.thumbnail((800, 800), Image.Resampling.LANCZOS)
    
    return np.array(pil_img)


async def extract_face_encoding(file: UploadFile, is_registration: bool = False) -> List[float]:
    """
    Read an uploaded image and return the first 128-d face encoding.
    Uses EXIF auto-orientation, 4-way rotation search (0°, 90°, 270°, 180°),
    and multi-scale upsampling to guarantee detection of mobile selfies.
    """
    contents = await file.read()
    if not contents:
        raise ValueError("Uploaded image is empty. Please capture a valid face photo.")

    if not USE_REAL_FR:
        raise ValueError("Face recognition engine is not installed on the server. Please ensure dlib/face_recognition is active.")

    try:
        base_image = load_and_orient_image(contents)
    except Exception as exc:
        logger.error("Failed to decode uploaded image: %s", exc)
        raise ValueError(f"Invalid image format: {exc}")

    # Check multiple rotations if standard orientation yields no face
    rotations = [0, 90, 270, 180]
    face_locations = []
    working_image = base_image

    for angle in rotations:
        if angle == 0:
            candidate_img = base_image
        elif angle == 90:
            candidate_img = np.rot90(base_image, 1)
        elif angle == 270:
            candidate_img = np.rot90(base_image, 3)
        elif angle == 180:
            candidate_img = np.rot90(base_image, 2)

        # 1. Standard HOG detection
        locs = face_recognition.face_locations(candidate_img, number_of_times_to_upsample=1, model="hog")
        if not locs:
            # 2. Multi-scale upsampling for smaller/distant faces
            locs = face_recognition.face_locations(candidate_img, number_of_times_to_upsample=2, model="hog")

        if locs:
            face_locations = locs
            working_image = candidate_img
            break

    if not face_locations:
        raise ValueError(
            "No face detected in photo. Please ensure your face is well-lit, upright, and clearly visible."
        )

    if len(face_locations) > 1:
        raise ValueError(
            f"Multiple faces detected in photo ({len(face_locations)} faces). Please ensure only one person is in the frame."
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🔒 ANTI-SPOOFING: Multi-Layer Liveness Detection (Verification only)
    # Detects photo/screen attacks:
    # 1. Screen bezels, window edges, monitor frames (Hough Transform)
    # 2. 2D FFT Moiré / LCD pixel grid frequency peaks
    # 3. Texture sharpness & variance anomalies
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if not is_registration:
        try:
            top, right, bottom, left = face_locations[0]
            import cv2

            gray_full = cv2.cvtColor(working_image, cv2.COLOR_RGB2GRAY)

            # ── Check 1: Screen Bezel / Border Detection (Hough Transform) ──
            # When someone aims a phone at a laptop/monitor/tablet, the frame contains
            # multiple long horizontal and vertical straight lines (screen edges, window borders).
            # Real selfies have natural organic curves (head, shoulders, neck) with almost zero lines.
            edges = cv2.Canny(gray_full, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=70, minLineLength=50, maxLineGap=10)
            screen_lines = 0
            if lines is not None:
                for line in lines:
                    pts = line[0] if len(line.shape) > 1 and line.shape[0] == 1 else line
                    x1, y1, x2, y2 = pts[0], pts[1], pts[2], pts[3]
                    # Skip lines entirely inside the face boundary
                    if left < x1 < right and top < y1 < bottom and left < x2 < right and top < y2 < bottom:
                        continue
                    angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
                    if angle < 6 or angle > 174 or (84 < angle < 96):
                        screen_lines += 1

            # ── Check 2: 2D FFT Moiré / Subpixel Grid Analysis ──
            face_region = working_image[top:bottom, left:right]
            high_freq_ratio = 0.0
            laplacian_var = 0.0
            texture_uniformity = 10.0
            mean_saturation = 50.0

            if face_region.size > 0:
                face_gray = cv2.cvtColor(face_region, cv2.COLOR_RGB2GRAY)
                face_resized = cv2.resize(face_gray, (128, 128))

                # FFT 2D high-frequency energy ratio
                f = np.fft.fft2(face_resized)
                fshift = np.fft.fftshift(f)
                h, w = face_resized.shape
                cy, cx = h // 2, w // 2
                radius = min(h, w) // 5
                y, x = np.ogrid[:h, :w]
                mask = (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2
                low_energy = np.sum(np.abs(fshift)[mask])
                total_energy = np.sum(np.abs(fshift))
                high_freq_ratio = float((total_energy - low_energy) / (total_energy + 1e-6))

                # Laplacian variance
                face_small = cv2.resize(face_gray, (64, 64))
                laplacian_var = float(cv2.Laplacian(face_small, cv2.CV_64F).var())

                # Texture uniformity across 4x4 blocks
                h_s, w_s = face_small.shape
                block_vars = []
                bh, bw = h_s // 4, w_s // 4
                for row in range(4):
                    for col in range(4):
                        block = face_small[row * bh:(row + 1) * bh, col * bw:(col + 1) * bw]
                        block_vars.append(float(np.std(block)))
                texture_uniformity = float(np.std(block_vars))

                # Saturation
                face_hsv = cv2.cvtColor(face_region, cv2.COLOR_RGB2HSV)
                mean_saturation = float(np.mean(face_hsv[:, :, 1]))

            logger.info(
                "[ANTI-SPOOF] screen_lines=%d, high_freq=%.4f, laplacian=%.2f, uniformity=%.2f",
                screen_lines, high_freq_ratio, laplacian_var, texture_uniformity
            )

            # ── Trigger anti-spoof rejection ──
            if screen_lines >= 6:
                logger.warning("[ANTI-SPOOF BLOCKED] Screen borders detected: %d lines", screen_lines)
                raise ValueError(
                    f"⚠️ Liveness Check Failed! Screen / monitor borders detected in frame ({screen_lines} straight edges). "
                    f"Showing photos on laptop/phone screens is strictly prohibited. Please show your live face directly."
                )

            if high_freq_ratio > 0.44:
                logger.warning("[ANTI-SPOOF BLOCKED] High Moiré / LCD pixel grid detected: %.4f", high_freq_ratio)
                raise ValueError(
                    "⚠️ Liveness Check Failed! Digital screen pixel lattice / Moiré pattern detected. "
                    "Showing photos on screens is not allowed. Please use your real face."
                )

            # Combined secondary flags
            spoof_flags = 0
            if laplacian_var > 700:
                spoof_flags += 1
            if texture_uniformity < 3.0:
                spoof_flags += 1
            if mean_saturation > 155:
                spoof_flags += 1

            if spoof_flags >= 2:
                logger.warning("[ANTI-SPOOF BLOCKED] Secondary texture flags: %d", spoof_flags)
                raise ValueError(
                    "⚠️ Liveness Check Failed! Artificial photo surface detected. "
                    "Please stand in front of the camera with your real face."
                )

        except ValueError:
            raise
        except Exception as spoof_exc:
            logger.warning("[ANTI-SPOOF] Check error (non-blocking): %s", spoof_exc)

    # Use 3 jitters during registration for a robust reference vector; 1 jitter for fast verification
    jitters = 3 if is_registration else 1
    encodings = face_recognition.face_encodings(
        working_image,
        known_face_locations=face_locations,
        num_jitters=jitters,
    )

    if not encodings:
        raise ValueError("Could not extract facial features. Please retake photo with clearer lighting.")

    return encodings[0].tolist()


def compute_match_confidence(distance: float, tolerance: float = FACE_MATCH_TOLERANCE) -> float:
    """Calculate an intuitive percentage match score (0-100%)."""
    if distance <= tolerance:
        score = 100.0 - (distance / tolerance) * 40.0
    else:
        score = max(0.0, 60.0 - ((distance - tolerance) / (1.0 - tolerance)) * 60.0)
    return round(score, 1)


def match_encoding(
    known_encoding: List[float],
    unknown_encoding: List[float],
    tolerance: float = FACE_MATCH_TOLERANCE,
) -> tuple[bool, float, float]:
    """Compare two face encodings. Returns (is_match, distance, confidence_percentage)."""
    known = np.array(known_encoding)
    unknown = np.array(unknown_encoding)
    if USE_REAL_FR:
        distance = float(face_recognition.face_distance([known], unknown)[0])
    else:
        distance = float(np.linalg.norm(known - unknown))
    is_match = distance <= tolerance
    confidence = compute_match_confidence(distance, tolerance)
    return is_match, distance, confidence

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


# ---------------------------------------------------------------------------
# College Roster Endpoints (7 Branches & 4 Years — A1 to G4)
# ---------------------------------------------------------------------------

@app.get("/roster/branches")
async def get_roster_branches():
    """
    Get the list of all 7 branches, their 28 sections (A1 to G4), and student enrollment counts.
    """
    db = await get_db()
    try:
        cur = await db.execute(
            """
            SELECT branch_code, section, year, COUNT(*) as student_count
            FROM college_roster
            GROUP BY branch_code, section, year
            ORDER BY branch_code, year, section
            """
        )
        section_rows = await cur.fetchall()

        cur_registered = await db.execute(
            """
            SELECT section, COUNT(*) as reg_count
            FROM students
            WHERE section != ''
            GROUP BY section
            """
        )
        reg_rows = await cur_registered.fetchall()
        reg_map = {r["section"]: r["reg_count"] for r in reg_rows}
    finally:
        await db.close()

    branch_map = {}
    all_sections = []

    for r in section_rows:
        b_code = r["branch_code"]
        sec = r["section"]
        b_meta = BRANCH_METADATA.get(b_code, {"name": "Engineering", "short": b_code})

        if b_code not in branch_map:
            branch_map[b_code] = {
                "code": b_code,
                "name": b_meta["name"],
                "short": b_meta["short"],
                "total_students": 0,
                "registered_students": 0,
                "sections": [],
            }

        sec_item = {
            "section": sec,
            "branch_code": b_code,
            "branch_name": b_meta["name"],
            "year": r["year"],
            "total_students": r["student_count"],
            "registered_students": reg_map.get(sec, 0),
        }
        branch_map[b_code]["total_students"] += r["student_count"]
        branch_map[b_code]["registered_students"] += reg_map.get(sec, 0)
        branch_map[b_code]["sections"].append(sec_item)
        all_sections.append(sec_item)

    return {
        "status": "success",
        "branches": list(branch_map.values()),
        "sections": all_sections,
    }


@app.get("/roster/students")
async def get_roster_students(
    section: str | None = None,
    branch_code: str | None = None,
    year: int | None = None,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    """
    Search or filter the college master student directory across branches and sections.
    """
    db = await get_db()
    try:
        query = """
            SELECT r.id, r.year, r.branch_code, r.branch_name, r.section, r.semester, 
                   r.class_roll_no, r.primary_roll_no, r.name,
                   (s.roll_no IS NOT NULL) as is_registered,
                   s.is_locked,
                   s.device_id
            FROM college_roster r
            LEFT JOIN students s ON r.primary_roll_no = s.roll_no
            WHERE 1=1
        """
        params = []

        if section:
            query += " AND r.section = ?"
            params.append(section.strip().upper())
        if branch_code:
            query += " AND r.branch_code = ?"
            params.append(branch_code.strip().upper())
        if year:
            query += " AND r.year = ?"
            params.append(year)
        if q:
            term = f"%{q.strip().upper()}%"
            query += " AND (r.name LIKE ? OR r.primary_roll_no LIKE ? OR r.class_roll_no LIKE ?)"
            params.extend([term, term, term])

        query += " ORDER BY r.section, CAST(r.class_roll_no AS INTEGER), r.primary_roll_no LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cur = await db.execute(query, params)
        rows = await cur.fetchall()

        # Get total count for pagination
        cnt_query = "SELECT COUNT(*) as total FROM college_roster r WHERE 1=1"
        cnt_params = []
        if section:
            cnt_query += " AND r.section = ?"
            cnt_params.append(section.strip().upper())
        if branch_code:
            cnt_query += " AND r.branch_code = ?"
            cnt_params.append(branch_code.strip().upper())
        if year:
            cnt_query += " AND r.year = ?"
            cnt_params.append(year)
        if q:
            term = f"%{q.strip().upper()}%"
            cnt_query += " AND (r.name LIKE ? OR r.primary_roll_no LIKE ? OR r.class_roll_no LIKE ?)"
            cnt_params.extend([term, term, term])

        cnt_cur = await db.execute(cnt_query, cnt_params)
        total_count = (await cnt_cur.fetchone())["total"]
    finally:
        await db.close()

    students = [
        {
            "id": r["id"],
            "year": r["year"],
            "branch_code": r["branch_code"],
            "branch_name": r["branch_name"],
            "section": r["section"],
            "semester": r["semester"],
            "class_roll_no": r["class_roll_no"],
            "primary_roll_no": r["primary_roll_no"],
            "name": r["name"],
            "is_registered": bool(r["is_registered"]),
            "is_locked": bool(r["is_locked"]) if r["is_locked"] is not None else None,
            "device_bound": bool(r["device_id"]),
        }
        for r in rows
    ]

    return {
        "status": "success",
        "total": total_count,
        "count": len(students),
        "students": students,
    }


@app.get("/roster/lookup/{roll_no:path}")
async def lookup_roster_student(roll_no: str):
    """
    Auto-lookup student information by Roll Number for 1-tap fast registration.
    Matches AKTU 13-digit roll number, section roll number (e.g. A1-01), or class roll.
    """
    clean_roll = roll_no.strip().upper()
    db = await get_db()
    try:
        cur = await db.execute(
            """
            SELECT r.id, r.year, r.branch_code, r.branch_name, r.section, r.semester, 
                   r.class_roll_no, r.primary_roll_no, r.name,
                   (s.roll_no IS NOT NULL) as is_registered,
                   s.is_locked,
                   s.device_id
            FROM college_roster r
            LEFT JOIN students s ON r.primary_roll_no = s.roll_no
            WHERE r.primary_roll_no = ? OR r.primary_roll_no LIKE ? OR (r.class_roll_no = ? AND ? != '')
            LIMIT 1
            """,
            (clean_roll, f"%{clean_roll}%", clean_roll, clean_roll),
        )
        row = await cur.fetchone()

        if not row:
            # Fallback: Search registered students directly
            stu_cur = await db.execute(
                "SELECT roll_no, name, branch_code, branch_name, section, year, class_roll_no, is_locked, device_id FROM students WHERE roll_no = ?",
                (clean_roll,),
            )
            stu_row = await stu_cur.fetchone()
            if stu_row:
                b_code = stu_row["branch_code"] or ""
                b_meta = BRANCH_METADATA.get(b_code, {"name": stu_row["branch_name"] or "Engineering"})
                return {
                    "status": "success",
                    "found": true,
                    "student": {
                        "name": stu_row["name"],
                        "primary_roll_no": stu_row["roll_no"],
                        "class_roll_no": stu_row["class_roll_no"] or "-",
                        "branch_code": b_code,
                        "branch_name": b_meta.get("name", ""),
                        "section": stu_row["section"] or "",
                        "year": stu_row["year"] or 1,
                        "semester": "",
                        "is_registered": true,
                        "is_locked": bool(stu_row["is_locked"]),
                        "device_bound": bool(stu_row["device_id"]),
                    },
                }

            return {
                "status": "success",
                "found": False,
                "message": f"Roll Number '{clean_roll}' not found in official college roster.",
            }

        return {
            "status": "success",
            "found": True,
            "student": {
                "name": row["name"],
                "primary_roll_no": row["primary_roll_no"],
                "class_roll_no": row["class_roll_no"],
                "branch_code": row["branch_code"],
                "branch_name": row["branch_name"],
                "section": row["section"],
                "year": row["year"],
                "semester": row["semester"],
                "is_registered": bool(row["is_registered"]),
                "is_locked": bool(row["is_locked"]) if row["is_locked"] is not None else None,
                "device_bound": bool(row["device_id"]),
            },
        }
    finally:
        await db.close()


@app.get("/roster/stats")
async def get_roster_stats():
    """Get high-level registration stats across all 7 branches & 4 years."""
    db = await get_db()
    try:
        tot_roster_cur = await db.execute("SELECT COUNT(*) FROM college_roster")
        total_roster = (await tot_roster_cur.fetchone())[0]

        tot_reg_cur = await db.execute("SELECT COUNT(*) FROM students")
        total_registered = (await tot_reg_cur.fetchone())[0]

        branch_cur = await db.execute(
            """
            SELECT r.branch_code, COUNT(r.id) as roster_count,
                   COUNT(s.roll_no) as registered_count
            FROM college_roster r
            LEFT JOIN students s ON r.primary_roll_no = s.roll_no
            GROUP BY r.branch_code
            ORDER BY r.branch_code
            """
        )
        branch_rows = await branch_cur.fetchall()
    finally:
        await db.close()

    branch_stats = []
    for r in branch_rows:
        b_code = r["branch_code"]
        b_meta = BRANCH_METADATA.get(b_code, {"name": "Engineering", "short": b_code})
        branch_stats.append({
            "branch_code": b_code,
            "branch_name": b_meta["name"],
            "short": b_meta["short"],
            "roster_count": r["roster_count"],
            "registered_count": r["registered_count"],
            "percentage": round((r["registered_count"] / r["roster_count"]) * 100, 1) if r["roster_count"] > 0 else 0,
        })

    return {
        "status": "success",
        "total_roster": total_roster,
        "total_registered": total_registered,
        "overall_percentage": round((total_registered / total_roster) * 100, 1) if total_roster > 0 else 0,
        "branches": branch_stats,
    }


# ---------------------------------------------------------------------------
# Student Registration, Login & Verification Endpoints
# ---------------------------------------------------------------------------

@app.post("/register")
async def register_student(
    roll_no: str = Form(..., description="Unique roll number of the student"),
    name: str = Form(..., description="Full name of the student"),
    photo: UploadFile = File(..., description="Selfie photo for face encoding generation"),
    device_id: str | None = Form(None, description="Unique Device UUID for hardware binding"),
    branch_code: str | None = Form(None, description="Branch Code (A-G)"),
    section: str | None = Form(None, description="Section (A1-G4)"),
    year: int | None = Form(None, description="Year (1-4)"),
    class_roll_no: str | None = Form(None, description="Class Roll Number"),
):
    """
    Register a new student or update existing profile if unlocked by Admin.
    Extracts 128-d face encoding, enriches profile with college roster info, and binds hardware device ID.
    Strictly enforces 1 Phone = 1 Student policy (Anti-Proxy Architecture).
    """
    clean_roll = roll_no.strip().upper()
    clean_name = name.strip().upper()
    clean_device = device_id.strip() if device_id else ""

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

        # Check if device is already registered to ANOTHER student
        if clean_device:
            dev_cur = await db.execute(
                "SELECT roll_no, name FROM students WHERE device_id = ? AND roll_no != ?",
                (clean_device, clean_roll),
            )
            dev_conflict = await dev_cur.fetchone()
            if dev_conflict:
                raise HTTPException(
                    status_code=403,
                    detail=f"Device Security Alert! This phone is permanently bound to {dev_conflict['name']} ({dev_conflict['roll_no']}). Multiple students cannot share one device. Please contact Teacher/Admin to reset device binding.",
                )

        # Auto-enrich from college_roster if fields are empty
        roster_cur = await db.execute(
            "SELECT branch_code, branch_name, section, year, class_roll_no, name FROM college_roster WHERE primary_roll_no = ? OR class_roll_no = ? LIMIT 1",
            (clean_roll, clean_roll),
        )
        r_row = await roster_cur.fetchone()

        final_branch = (branch_code or (r_row["branch_code"] if r_row else "")).strip().upper()
        final_section = (section or (r_row["section"] if r_row else "")).strip().upper()
        final_year = year if year is not None else (r_row["year"] if r_row else 1)
        final_class_roll = (class_roll_no or (r_row["class_roll_no"] if r_row else "")).strip()
        final_branch_name = BRANCH_METADATA.get(final_branch, {}).get("name", (r_row["branch_name"] if r_row else ""))

        # Check for existing student
        cursor = await db.execute(
            "SELECT roll_no, name, is_locked, device_id FROM students WHERE roll_no = ?", (clean_roll,)
        )
        existing = await cursor.fetchone()

        # Security Protection: If student already exists and is locked, block re-registration
        if existing and (existing["is_locked"] is None or existing["is_locked"] == 1):
            raise HTTPException(
                status_code=403,
                detail=f"Roll Number '{clean_roll}' is already locked with a registered biometric profile. Re-registration is blocked for security. Please ask your Teacher/Admin from dashboard to unlock your biometrics.",
            )

        try:
            encoding = await extract_face_encoding(photo, is_registration=True)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        encoding_json = json.dumps(encoding)
        now_iso = datetime.now().isoformat()

        if existing:
            # Re-enroll student (previously unlocked by admin) and lock
            await db.execute(
                """
                UPDATE students SET
                    name = ?,
                    face_encoding = ?,
                    is_locked = 1,
                    updated_at = ?,
                    branch_code = CASE WHEN ? != '' THEN ? ELSE branch_code END,
                    branch_name = CASE WHEN ? != '' THEN ? ELSE branch_name END,
                    section = CASE WHEN ? != '' THEN ? ELSE section END,
                    year = ?,
                    class_roll_no = CASE WHEN ? != '' THEN ? ELSE class_roll_no END,
                    device_id = CASE WHEN ? != '' THEN ? ELSE device_id END
                WHERE roll_no = ?
                """,
                (
                    clean_name,
                    encoding_json,
                    now_iso,
                    final_branch, final_branch,
                    final_branch_name, final_branch_name,
                    final_section, final_section,
                    final_year,
                    final_class_roll, final_class_roll,
                    clean_device, clean_device,
                    clean_roll,
                ),
            )
            await db.commit()
            return {
                "status": "success",
                "is_update": True,
                "message": f"Biometric profile & device binding for '{clean_name}' (Roll No: {clean_roll}, Section: {final_section}) updated and locked successfully.",
                "student": {
                    "roll_no": clean_roll,
                    "name": clean_name,
                    "branch_code": final_branch,
                    "branch_name": final_branch_name,
                    "section": final_section,
                    "year": final_year,
                    "class_roll_no": final_class_roll,
                },
            }

        # New registration: Insert, bind device, and lock permanently
        await db.execute(
            """
            INSERT INTO students 
            (roll_no, name, face_encoding, is_locked, created_at, updated_at, device_id, branch_code, branch_name, section, year, class_roll_no)
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean_roll, clean_name, encoding_json, now_iso, now_iso, clean_device,
                final_branch, final_branch_name, final_section, final_year, final_class_roll,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    return {
        "status": "success",
        "is_update": False,
        "message": f"Student '{clean_name}' (Roll No: {clean_roll}, Section: {final_section}) enrolled and bound to device successfully.",
        "student": {
            "roll_no": clean_roll,
            "name": clean_name,
            "branch_code": final_branch,
            "branch_name": final_branch_name,
            "section": final_section,
            "year": final_year,
            "class_roll_no": final_class_roll,
        },
    }


@app.post("/students/login")
async def login_student(
    roll_no: str = Form(..., description="Student Roll Number (AKTU Roll or Section Roll)"),
    device_id: str = Form(..., description="Mobile hardware device UUID"),
):
    """
    Authenticate and lock student profile to mobile hardware device.
    Strictly enforces 1 Phone = 1 Student policy (Anti-Proxy Architecture).
    """
    clean_roll = roll_no.strip().upper()
    clean_device = device_id.strip()

    if not clean_device:
        raise HTTPException(status_code=400, detail="Device UUID is required for hardware security binding.")

    db = await get_db()
    try:
        # 1. Check if this device is already bound to ANOTHER student
        dev_cur = await db.execute(
            "SELECT roll_no, name FROM students WHERE device_id = ? AND roll_no != ?",
            (clean_device, clean_roll),
        )
        other_student = await dev_cur.fetchone()
        if other_student:
            raise HTTPException(
                status_code=403,
                detail=f"Device Security Alert! This phone is permanently bound to {other_student['name']} ({other_student['roll_no']}). Multiple students cannot share the same device. Proxy login blocked.",
            )

        # 2. Check student record in registered students
        cur = await db.execute(
            "SELECT roll_no, name, branch_code, branch_name, section, year, class_roll_no, is_locked, device_id FROM students WHERE roll_no = ?",
            (clean_roll,),
        )
        student = await cur.fetchone()

        if not student:
            # Check college roster fallback
            roster_cur = await db.execute(
                "SELECT primary_roll_no as roll_no, name, branch_code, branch_name, section, year, class_roll_no FROM college_roster WHERE primary_roll_no = ? OR class_roll_no = ? LIMIT 1",
                (clean_roll, clean_roll),
            )
            r_stu = await roster_cur.fetchone()
            if not r_stu:
                raise HTTPException(status_code=404, detail=f"Roll Number '{clean_roll}' not found in college records.")

            raise HTTPException(
                status_code=404,
                detail=f"Student '{r_stu['name']}' ({clean_roll}) is in college roster but has not registered biometrics yet. Please complete Face Registration first.",
            )

        registered_dev = (student["device_id"] or "").strip()

        # 3. Check if student is bound to a DIFFERENT device
        if registered_dev and registered_dev != clean_device:
            raise HTTPException(
                status_code=403,
                detail=f"Device Binding Alert! Student profile for '{student['name']}' ({clean_roll}) is locked to another phone. You cannot login from multiple devices. Contact Teacher/Admin from dashboard to reset device binding.",
            )

        # 4. If student has no device bound yet, bind this device now!
        if not registered_dev:
            await db.execute(
                "UPDATE students SET device_id = ? WHERE roll_no = ?",
                (clean_device, clean_roll),
            )
            await db.commit()
            logger.info("Bound student %s to device %s", clean_roll, clean_device)

        b_code = student["branch_code"] or ""
        b_name = student["branch_name"] or BRANCH_METADATA.get(b_code, {}).get("name", "")

        return {
            "status": "success",
            "message": f"Device bound and authenticated successfully for {student['name']}.",
            "student": {
                "roll_no": student["roll_no"],
                "name": student["name"],
                "branch_code": b_code,
                "branch_name": b_name,
                "section": student["section"] or "",
                "year": student["year"] or 1,
                "class_roll_no": student["class_roll_no"] or "",
                "is_locked": bool(student["is_locked"]),
                "device_id": clean_device,
            },
        }
    finally:
        await db.close()


@app.post("/verify")
async def verify_attendance(
    photo: UploadFile = File(..., description="Selfie photo for live verification"),
    roll_no: str | None = Form(None, description="Optional Roll Number for faster 1-to-1 matching"),
    device_id: str | None = Form(None, description="Optional Device UUID for hardware binding verification"),
):
    """
    Verify a student's identity and mark attendance.
    If roll_no is provided, it performs a 1-to-1 verification against the registered encoding.
    Enforces hardware device lock (Anti-Proxy) and strict time windows.
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
                "SELECT roll_no, name, face_encoding, device_id, branch_code, section, year FROM students WHERE roll_no = ?",
                (clean_roll,),
            )
            student = await cursor.fetchone()
            if not student:
                raise HTTPException(
                    status_code=404,
                    detail=f"Student with Roll Number '{clean_roll}' is not enrolled on this server.",
                )

            # Device Binding Security Check (1 Student = 1 Phone Lock)
            registered_dev = (student["device_id"] or "").strip()
            incoming_dev = (device_id or "").strip()

            # Check if incoming device belongs to another student
            if incoming_dev:
                dev_cur = await db.execute(
                    "SELECT roll_no, name FROM students WHERE device_id = ? AND roll_no != ?",
                    (incoming_dev, clean_roll),
                )
                dev_conflict = await dev_cur.fetchone()
                if dev_conflict:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Device Security Alert! This phone is bound to {dev_conflict['name']} ({dev_conflict['roll_no']}). Proxy attendance for {student['name']} is strictly blocked.",
                    )

            known_encoding = json.loads(student["face_encoding"])
            is_match, distance, _ = match_encoding(known_encoding, unknown_encoding)
            logger.info(
                "1-to-1 Verification: roll=%s, name=%s, distance=%.4f (threshold=%.2f)",
                clean_roll,
                student["name"],
                distance,
                FACE_MATCH_TOLERANCE,
            )
            
            if is_match:
                matched_roll_no = student["roll_no"]
                matched_name = student["name"]
                matched_section = student["section"] or ""
                matched_branch = student["branch_code"] or ""
                matched_year = student["year"] or 1
                match_distance = distance
                match_confidence = max(0.0, round((1.0 - (distance / FACE_MATCH_TOLERANCE)) * 100.0, 2))

                if match_confidence < 35.0:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Face match confidence too low ({match_confidence:.1f}% < 35%). Live photo does not match {student['name']} with high fidelity. Showing photos on screens or printouts is strictly blocked.",
                    )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Face mismatch! (Distance: {distance:.4f}). This does not appear to be {student['name']}. Proxy attendance blocked.",
                )
        else:
            # ── 1:N Global Search Verification ──
            cursor = await db.execute("SELECT roll_no, name, face_encoding, device_id, branch_code, section, year FROM students")
            all_students = await cursor.fetchall()

            if not all_students:
                raise HTTPException(
                    status_code=404,
                    detail="No students enrolled. Please register first.",
                )

            best_match = None
            best_distance = FACE_MATCH_TOLERANCE
            
            for stu in all_students:
                known_encoding = json.loads(stu["face_encoding"])
                is_match, distance, _ = match_encoding(known_encoding, unknown_encoding)
                if is_match and distance < best_distance:
                    best_distance = distance
                    best_match = stu

            if best_match:
                matched_roll_no = best_match["roll_no"]
                matched_name = best_match["name"]
                matched_section = best_match["section"] or ""
                matched_branch = best_match["branch_code"] or ""
                matched_year = best_match["year"] or 1
                student = best_match
                match_distance = best_distance
                match_confidence = max(0.0, round((1.0 - (best_distance / FACE_MATCH_TOLERANCE)) * 100.0, 2))

                if match_confidence < 35.0:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Face match confidence too low ({match_confidence:.1f}% < 35%). Live photo does not match registered biometric records with high fidelity. Screen/photo attendance blocked.",
                    )
                
                registered_dev = (student["device_id"] or "").strip()
                incoming_dev = (device_id or "").strip()

                if incoming_dev:
                    dev_cur = await db.execute(
                        "SELECT roll_no, name FROM students WHERE device_id = ? AND roll_no != ?",
                        (incoming_dev, matched_roll_no),
                    )
                    dev_conflict = await dev_cur.fetchone()
                    if dev_conflict:
                        raise HTTPException(
                            status_code=403,
                            detail=f"Device Security Alert! This phone is bound to {dev_conflict['name']} ({dev_conflict['roll_no']}). Proxy attendance for {student['name']} is strictly blocked.",
                        )
            else:
                raise HTTPException(
                    status_code=404,
                    detail="Face not recognized among registered students. Please ensure good lighting and look directly at the camera.",
                )

        if registered_dev and incoming_dev and registered_dev != incoming_dev:
            logger.warning(
                "Device Mismatch: student=%s, registered_device=%s, incoming_device=%s",
                matched_roll_no,
                registered_dev,
                incoming_dev,
            )
            raise HTTPException(
                status_code=403,
                detail=f"Device Security Alert! Attendance for {student['name']} ({matched_roll_no}) is bound to another phone. Proxy attendance from different devices is strictly blocked.",
            )

        # Auto-bind device on first verify if unassigned
        if not registered_dev and incoming_dev:
            await db.execute("UPDATE students SET device_id = ? WHERE roll_no = ?", (incoming_dev, matched_roll_no))
            await db.commit()

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
                "section": matched_section,
                "branch_code": matched_branch,
                "year": matched_year,
                "confidence": match_confidence,
                "distance": round(match_distance, 3),
            }

        # --- Mark attendance ---
        now_time_str = now.strftime("%H:%M:%S")
        await db.execute(
            "INSERT INTO attendance (roll_no, date, time, subject, status, section, branch_code, year) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (matched_roll_no, today, now_time_str, current_subject, "Present", matched_section, matched_branch, matched_year),
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
        "section": matched_section,
        "branch_code": matched_branch,
        "year": matched_year,
        "date": today,
        "time": now_time_str,
        "confidence": match_confidence,
        "distance": round(match_distance, 3),
    }


@app.get("/attendance")
async def get_attendance(
    roll_no: str | None = None,
    date_filter: str | None = None,
    subject_filter: str | None = None,
    branch_filter: str | None = None,
    section_filter: str | None = None,
):
    """
    Retrieve attendance records, optionally filtered by student, date, subject, branch, and section.
    """
    db = await get_db()
    try:
        query = """
            SELECT a.roll_no, s.name, a.date, a.time, a.subject, a.status,
                   COALESCE(s.branch_code, a.branch_code, '') as branch_code,
                   COALESCE(s.section, a.section, '') as section,
                   COALESCE(s.class_roll_no, '') as class_roll_no
            FROM attendance a 
            JOIN students s ON a.roll_no = s.roll_no 
            WHERE 1=1
        """
        params: list = []

        if roll_no:
            query += " AND a.roll_no = ?"
            params.append(roll_no.strip().upper())
        if date_filter:
            query += " AND a.date = ?"
            params.append(date_filter.strip())
        if subject_filter:
            query += " AND (a.subject = ? OR a.subject LIKE ?)"
            params.extend([subject_filter.strip(), f"%{subject_filter.strip()}%"])
        if branch_filter:
            query += " AND (s.branch_code = ? OR a.branch_code = ?)"
            params.extend([branch_filter.strip().upper(), branch_filter.strip().upper()])
        if section_filter:
            query += " AND (s.section = ? OR a.section = ?)"
            params.extend([section_filter.strip().upper(), section_filter.strip().upper()])

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
            "branch_code": row["branch_code"],
            "branch_name": BRANCH_METADATA.get(row["branch_code"], {}).get("name", ""),
            "section": row["section"],
            "class_roll_no": row["class_roll_no"],
        }
        for row in rows
    ]

    return {"status": "success", "count": len(records), "records": records}


@app.get("/students")
async def list_students(
    branch_code: str | None = None,
    section: str | None = None,
    q: str | None = None,
):
    """List all registered students with biometric lock status, branch, and section."""
    db = await get_db()
    try:
        query = "SELECT roll_no, name, is_locked, device_id, branch_code, branch_name, section, year, class_roll_no, created_at, updated_at FROM students WHERE 1=1"
        params = []
        if branch_code:
            query += " AND branch_code = ?"
            params.append(branch_code.strip().upper())
        if section:
            query += " AND section = ?"
            params.append(section.strip().upper())
        if q:
            term = f"%{q.strip().upper()}%"
            query += " AND (name LIKE ? OR roll_no LIKE ? OR class_roll_no LIKE ?)"
            params.extend([term, term, term])

        query += " ORDER BY section, CAST(class_roll_no AS INTEGER), roll_no"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
    finally:
        await db.close()

    students = [
        {
            "roll_no": row["roll_no"],
            "name": row["name"],
            "is_locked": bool(row["is_locked"]) if row["is_locked"] is not None else True,
            "device_bound": bool(row["device_id"]),
            "branch_code": row["branch_code"] or "",
            "branch_name": row["branch_name"] or BRANCH_METADATA.get(row["branch_code"] or "", {}).get("name", ""),
            "section": row["section"] or "",
            "year": row["year"] or 1,
            "class_roll_no": row["class_roll_no"] or "",
            "created_at": row["created_at"] or "",
            "updated_at": row["updated_at"] or "",
        }
        for row in rows
    ]
    return {"status": "success", "count": len(students), "students": students}


@app.post("/admin/students/{roll_no:path}/unlock")
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


@app.post("/admin/students/{roll_no:path}/lock")
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


@app.get("/students/{roll_no:path}")
async def get_student_profile(roll_no: str):
    """Fetch student profile by roll number to restore local session after app reinstall."""
    clean_roll = roll_no.strip().upper()
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT roll_no, name, branch_code, branch_name, section, year, class_roll_no, is_locked, device_id 
            FROM students WHERE roll_no = ?
            """,
            (clean_roll,),
        )
        student = await cursor.fetchone()
        if not student:
            # Fallback check college_roster
            roster_cur = await db.execute(
                "SELECT primary_roll_no as roll_no, name, branch_code, branch_name, section, year, class_roll_no FROM college_roster WHERE primary_roll_no = ? OR class_roll_no = ? LIMIT 1",
                (clean_roll, clean_roll),
            )
            r_stu = await roster_cur.fetchone()
            if not r_stu:
                raise HTTPException(
                    status_code=404,
                    detail=f"No registered student found with Roll Number '{clean_roll}'.",
                )
            b_code = r_stu["branch_code"]
            return {
                "status": "success",
                "roll_no": r_stu["roll_no"],
                "name": r_stu["name"],
                "branch_code": b_code,
                "branch_name": r_stu["branch_name"] or BRANCH_METADATA.get(b_code, {}).get("name", ""),
                "section": r_stu["section"] or "",
                "year": r_stu["year"] or 1,
                "class_roll_no": r_stu["class_roll_no"] or "",
                "is_locked": False,
                "device_id": "",
            }

        b_code = student["branch_code"] or ""
        return {
            "status": "success",
            "roll_no": student["roll_no"],
            "name": student["name"],
            "branch_code": b_code,
            "branch_name": student["branch_name"] or BRANCH_METADATA.get(b_code, {}).get("name", ""),
            "section": student["section"] or "",
            "year": student["year"] or (int(student["section"][1]) if student["section"] and len(student["section"]) >= 2 and student["section"][1].isdigit() else 1),
            "class_roll_no": student["class_roll_no"] or "",
            "is_locked": bool(student["is_locked"]) if student["is_locked"] is not None else True,
            "device_id": student["device_id"] or "",
        }
    finally:
        await db.close()


@app.delete("/students/{roll_no:path}")
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


@app.post("/admin/students/{roll_no:path}/reset-device")
async def reset_student_device(roll_no: str):
    """Admin resets student hardware device binding so they can bind a new phone."""
    clean_roll = roll_no.strip().upper()
    db = await get_db()
    try:
        cur = await db.execute("UPDATE students SET device_id = '' WHERE roll_no = ?", (clean_roll,))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Student with roll number '{clean_roll}' not found.")
    finally:
        await db.close()
    return {"status": "success", "message": f"Device binding for student '{clean_roll}' reset. Next login will bind to their new phone."}


@app.get("/students/{roll_no:path}/analytics")
async def get_student_attendance_analytics(roll_no: str):
    """
    Calculate personal attendance metrics, subject-wise percentages,
    75% shortage alerts, and chronological attendance history for a student.
    """
    clean_roll = roll_no.strip().upper()
    db = await get_db()
    try:
        # Check student exists
        cursor = await db.execute("SELECT roll_no, name FROM students WHERE roll_no = ?", (clean_roll,))
        student = await cursor.fetchone()
        if not student:
            raise HTTPException(status_code=404, detail=f"Student with Roll Number '{clean_roll}' not found.")

        # Get all attendance records for this student
        cur_att = await db.execute(
            """
            SELECT date, time, subject, status
            FROM attendance
            WHERE roll_no = ?
            ORDER BY date DESC, time DESC
            """,
            (clean_roll,),
        )
        records = await cur_att.fetchall()

        # Get total classes held across the institution per subject
        cur_total_classes = await db.execute(
            """
            SELECT subject, COUNT(DISTINCT date) as total_held
            FROM attendance
            WHERE subject != ''
            GROUP BY subject
            """
        )
        total_held_rows = await cur_total_classes.fetchall()
        total_held_map = {row["subject"]: max(1, row["total_held"]) for row in total_held_rows}

        # Subject-wise attendance calculation for this student
        subject_attended: dict[str, int] = {}
        for r in records:
            subj = (r["subject"] or "General Class").strip()
            subject_attended[subj] = subject_attended.get(subj, 0) + 1

        # Also include subjects from timetable if not yet held
        cur_tt = await db.execute("SELECT DISTINCT subject FROM timetable WHERE subject != ''")
        tt_subjects = [row["subject"] for row in await cur_tt.fetchall()]
        for subj in tt_subjects:
            clean_subj = subj.strip()
            if clean_subj not in total_held_map:
                total_held_map[clean_subj] = 0

        subjects_summary = []
        shortage_subjects = []
        total_attended_all = len(records)
        total_held_all = sum(total_held_map.values()) if total_held_map else max(1, total_attended_all)
        if total_held_all == 0:
            total_held_all = max(1, total_attended_all)

        for subj, held in total_held_map.items():
            attended = subject_attended.get(subj, 0)
            effective_held = held if held > 0 else (attended if attended > 0 else 1)
            percentage = round((attended / effective_held) * 100, 1) if effective_held > 0 else 100.0
            percentage = min(100.0, percentage)
            is_shortage = percentage < 75.0 and effective_held >= 3

            subj_data = {
                "subject": subj,
                "attended": attended,
                "total_held": effective_held,
                "percentage": percentage,
                "shortage": is_shortage,
            }
            subjects_summary.append(subj_data)
            if is_shortage:
                shortage_subjects.append(subj)

        overall_pct = round((total_attended_all / total_held_all) * 100, 1) if total_held_all > 0 else 100.0
        overall_pct = min(100.0, overall_pct)

        return {
            "status": "success",
            "student": {
                "roll_no": student["roll_no"],
                "name": student["name"],
            },
            "overall_percentage": overall_pct,
            "total_attended": total_attended_all,
            "total_held": total_held_all,
            "is_shortage": overall_pct < 75.0,
            "shortage_subjects": shortage_subjects,
            "subjects": sorted(subjects_summary, key=lambda x: x["subject"]),
            "records": [
                {
                    "date": r["date"],
                    "time": r["time"],
                    "subject": r["subject"] or "General Class",
                    "status": r["status"],
                }
                for r in records
            ],
        }
    finally:
        await db.close()



# ---------------------------------------------------------------------------
# End-of-class reporting
# ---------------------------------------------------------------------------

@app.post("/end_class")
async def end_class(
    subject: str | None = Form(None, description="Override subject name (auto-detected from timetable if omitted)"),
    teacher_email: str | None = Form(None, description="Override teacher email (auto-detected from timetable if omitted)"),
    section: str | None = Form(None, description="Optional Section filter (e.g. A1, B2)"),
    branch: str | None = Form(None, description="Optional Branch filter (e.g. A, B)"),
    year: int | None = Form(None, description="Optional Year filter (1, 2, 3, 4)"),
):
    """
    Trigger the end-of-class workflow:
    1. Resolve the class from timetable or overrides.
    2. Generate an Excel report with Year, Branch, Section, Class Roll, and AKTU Roll.
    3. Email the report to the teacher if configured.
    """
    now = datetime.now()
    today = date.today().isoformat()

    # --- Resolve class info from timetable or form overrides ---
    resolved_section = (section and section.strip().upper()) or ""
    resolved_branch = (branch and branch.strip().upper()) or ""
    class_info = await get_class_info_from_db(now, section=resolved_section or None, branch_code=resolved_branch or None, year=year)

    resolved_subject = (subject and subject.strip()) or (class_info["subject"] if class_info else None)
    resolved_email = (teacher_email and teacher_email.strip()) or (class_info["teacher_email"] if class_info else None)
    if not resolved_section and class_info and class_info.get("section"):
        resolved_section = class_info["section"]
    if not resolved_branch and class_info and class_info.get("branch_code"):
        resolved_branch = class_info["branch_code"]
    resolved_year = year or (class_info.get("year") if class_info and class_info.get("year") else (int(resolved_section[1]) if len(resolved_section) >= 2 and resolved_section[1].isdigit() else None))

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
        excel_path, filename = await generate_attendance_excel(
            today, resolved_subject, section=resolved_section or None, branch=resolved_branch or None, year=resolved_year
        )
    except Exception as exc:
        logger.exception("Failed to generate Excel report")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating attendance report: {exc}",
        )

    download_url = f"/reports/{filename}"
    email_sent = False
    email_error = None
    year_str = get_year_label(resolved_year, resolved_section)

    # Check if SMTP credentials are configured (not default placeholders)
    if SMTP_USER and SMTP_USER != "your_email@gmail.com" and SMTP_PASSWORD and SMTP_PASSWORD != "your_app_password":
        try:
            sec_info = f" ({year_str} • Section {resolved_section})" if resolved_section else (f" ({year_str})" if resolved_year else "")
            send_email_with_attachment(
                to_email=resolved_email,
                subject_line=f"Attendance Report — {resolved_subject}{sec_info} — {today}",
                body=(
                    f"Dear Professor,\n\n"
                    f"Please find attached the official attendance report for "
                    f"'{resolved_subject}'{sec_info} held on {today}.\n\n"
                    f"Academic Year: {year_str}\n"
                    f"Branch: {BRANCH_METADATA.get(resolved_branch, {}).get('name', resolved_branch or 'All Branches')}\n"
                    f"Section: {resolved_section or 'All Sections'}\n\n"
                    f"This report was auto-generated by the Smart Attendance System.\n\n"
                    f"Regards,\n"
                    f"IERT Smart Attendance Bot"
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
        msg = f"Attendance report for '{resolved_subject}' ({year_str}) generated & emailed to {resolved_email}."
    else:
        msg = f"Excel attendance report for {year_str} generated! (Email skipped: {email_error}). Downloading sheet..."

    return {
        "status": "success" if email_sent else "excel_ready",
        "message": msg,
        "subject": resolved_subject,
        "section": resolved_section,
        "branch": resolved_branch,
        "year": resolved_year,
        "year_label": year_str,
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
async def view_timetable(
    section: str | None = None,
    branch_code: str | None = None,
    year: int | None = None,
):
    """Return the full timetable with strict attendance windows, branches, years, sections, and current class status."""
    now = datetime.now()
    current_class = await get_class_info_from_db(now, section=section, branch_code=branch_code, year=year)

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
                SELECT id, day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email, 
                       COALESCE(section, '') as section, COALESCE(branch_code, '') as branch_code,
                       COALESCE(branch_name, '') as branch_name, COALESCE(year, 0) as year
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
                eh = r["end_hour"]
                em = r["end_minute"]
                we_h = h + (sm + wm) // 60
                we_m = (sm + wm) % 60
                
                if eh is not None and em is not None:
                    time_lbl = f"{h:02d}:{sm:02d} - {eh:02d}:{em:02d}"
                    att_window = f"{h:02d}:{sm:02d} - {eh:02d}:{em:02d} (Strict)"
                else:
                    time_lbl = f"{h:02d}:{sm:02d} - {h:02d}:59"
                    att_window = f"{h:02d}:{sm:02d} - {we_h:02d}:{we_m:02d} ({wm} min window)"

                b_code = r["branch_code"] or ""
                b_name = r["branch_name"] or BRANCH_METADATA.get(b_code, {}).get("name", "")
                sec = r["section"] or ""
                y_val = r["year"] or (int(sec[1]) if len(sec) >= 2 and sec[1].isdigit() else 0)
                schedule.append({
                    "id": r["id"],
                    "day": r["day"],
                    "hour": h,
                    "start_minute": sm,
                    "allowed_window_minutes": wm,
                    "end_hour": eh,
                    "end_minute": em,
                    "time_label": time_lbl,
                    "attendance_window": att_window,
                    "subject": r["subject"],
                    "teacher_email": r["teacher_email"],
                    "branch_code": b_code,
                    "branch_name": b_name,
                    "year": y_val,
                    "year_label": get_year_label(y_val, sec) if y_val else "All Years",
                    "section": sec or "All Sections",
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
                "branch_code": info.get("branch_code", ""),
                "branch_name": info.get("branch_name", ""),
                "year": info.get("year", 0),
                "year_label": get_year_label(info.get("year"), info.get("section")) if info.get("year") else "All Years",
                "section": info.get("section", "All Sections"),
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
    end_hour: int | None = Form(None, ge=0, le=23, description="Class end hour (0-23)"),
    end_minute: int | None = Form(None, ge=0, le=59, description="Class end minute (0-59)"),
    allowed_window_minutes: int = Form(10, ge=1, le=240, description="Allowed attendance window in minutes (default 10)"),
    subject: str = Form(..., description="Subject name"),
    teacher_email: str = Form(..., description="Teacher email address"),
    branch_code: str | None = Form("", description="Optional branch code (A to G)"),
    year: int | None = Form(0, description="Optional year (1, 2, 3, 4)"),
    section: str | None = Form("", description="Optional section (e.g. A1, B2)"),
):
    """Add or update a class in the timetable with branch, year, section, and strict allowed attendance window."""
    clean_day = day.strip().capitalize()
    clean_subject = subject.strip()
    clean_email = teacher_email.strip()
    clean_section = (section or "").strip().upper()
    clean_branch = (branch_code or "").strip().upper()
    
    # Infer branch & year from section if not explicitly provided
    if clean_section and not clean_branch and len(clean_section) >= 1:
        clean_branch = clean_section[0]
    final_year = year if (year and year > 0) else (int(clean_section[1]) if len(clean_section) >= 2 and clean_section[1].isdigit() else 0)
    branch_name = BRANCH_METADATA.get(clean_branch, {}).get("name", "")

    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO timetable (day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email, section, branch_code, branch_name, year)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(day, hour) DO UPDATE SET
                start_minute = excluded.start_minute,
                end_hour = excluded.end_hour,
                end_minute = excluded.end_minute,
                allowed_window_minutes = excluded.allowed_window_minutes,
                subject = excluded.subject,
                teacher_email = excluded.teacher_email,
                section = excluded.section,
                branch_code = excluded.branch_code,
                branch_name = excluded.branch_name,
                year = excluded.year
            """,
            (clean_day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, clean_subject, clean_email, clean_section, clean_branch, branch_name, final_year),
        )
        await db.commit()

        # Keep memory cache updated
        TIMETABLE[(clean_day, hour)] = {
            "subject": clean_subject,
            "teacher_email": clean_email,
            "start_minute": start_minute,
            "end_hour": end_hour,
            "end_minute": end_minute,
            "allowed_window_minutes": allowed_window_minutes,
            "section": clean_section,
            "branch_code": clean_branch,
            "branch_name": branch_name,
            "year": final_year,
        }
    finally:
        await db.close()

    yr_label = f" ({get_year_label(final_year, clean_section)})" if final_year else ""
    return {
        "status": "success",
        "message": f"Class '{clean_subject}' for {branch_name or clean_branch or 'General'}{yr_label} (Section: {clean_section or 'All Sections'}) on {clean_day} at {hour:02d}:{start_minute:02d} saved successfully.",
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


