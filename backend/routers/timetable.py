from fastapi import APIRouter, Form, HTTPException, UploadFile, File
from typing import Optional
from datetime import datetime, date
import json
from database import get_db
from config import BRANCH_METADATA, FACE_MATCH_TOLERANCE, TIMETABLE, ATTENDANCE_WINDOW_MINUTES
from utils import get_year_label
from schemas import AttendanceUpdate, AttendanceManualCreate, StudentProfileUpdate
from services.face_engine import extract_face_encoding, match_encoding, compute_match_confidence
from services.timetable_service import get_class_info_from_db, check_attendance_window
from services.report_service import generate_attendance_excel, send_email_with_attachment
import logging
logger = logging.getLogger('attendance')

router = APIRouter(tags=['timetable'])

@router.get('/timetable')
async def view_timetable(
    section: str | None = None,
    branch_code: str | None = None,
    year: int | None = None,
):
    """Return the timetable filtered by section/branch (or full schedule for admin) with strict attendance windows."""
    clean_sec = section.strip().upper() if section and section.strip() else None
    clean_branch = branch_code.strip().upper() if branch_code and branch_code.strip() else None

    # Infer branch & year from section if missing
    if clean_sec and len(clean_sec) >= 2:
        if not clean_branch:
            clean_branch = clean_sec[0]
        if not year and clean_sec[1].isdigit():
            year = int(clean_sec[1])

    now = datetime.now()
    current_class = await get_class_info_from_db(now, section=clean_sec, branch_code=clean_branch, year=year)

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
            where_clauses = []
            params = []

            # If section is provided: Show (1) classes specifically for this section, OR
            # (2) classes for 'All Sections' (empty / ALL) matching branch
            if clean_sec:
                if clean_branch and year:
                    where_clauses.append(
                        """
                        (
                            UPPER(section) = ?
                            OR (
                                (section IS NULL OR section = '' OR UPPER(section) = 'ALL' OR UPPER(section) = 'ALL SECTIONS')
                                AND (branch_code IS NULL OR branch_code = '' OR UPPER(branch_code) = 'ALL' OR UPPER(branch_code) = 'ALL BRANCHES' OR UPPER(branch_code) = ?)
                                AND (year IS NULL OR year = 0 OR year = ?)
                            )
                        )
                        """
                    )
                    params.extend([clean_sec, clean_branch, year])
                elif clean_branch:
                    where_clauses.append(
                        """
                        (
                            UPPER(section) = ?
                            OR (
                                (section IS NULL OR section = '' OR UPPER(section) = 'ALL' OR UPPER(section) = 'ALL SECTIONS')
                                AND (branch_code IS NULL OR branch_code = '' OR UPPER(branch_code) = 'ALL' OR UPPER(branch_code) = 'ALL BRANCHES' OR UPPER(branch_code) = ?)
                            )
                        )
                        """
                    )
                    params.extend([clean_sec, clean_branch])
                else:
                    where_clauses.append(
                        """
                        (
                            UPPER(section) = ?
                            OR (section IS NULL OR section = '' OR UPPER(section) = 'ALL' OR UPPER(section) = 'ALL SECTIONS')
                        )
                        """
                    )
                    params.append(clean_sec)
            elif clean_branch:
                if year:
                    where_clauses.append(
                        """
                        (
                            (UPPER(branch_code) = ? OR branch_code IS NULL OR branch_code = '' OR UPPER(branch_code) = 'ALL')
                            AND (year = ? OR year = 0)
                        )
                        """
                    )
                    params.extend([clean_branch, year])
                else:
                    where_clauses.append("(UPPER(branch_code) = ? OR branch_code IS NULL OR branch_code = '' OR UPPER(branch_code) = 'ALL')")
                    params.append(clean_branch)

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            query = f"""
                SELECT id, day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email, 
                       COALESCE(section, '') as section, COALESCE(branch_code, '') as branch_code,
                       COALESCE(branch_name, '') as branch_name, COALESCE(year, 0) as year
                FROM timetable
                {where_sql}
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
            cursor = await db.execute(query, params)
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

    # Only fall back to default general timetable if NO student filter was applied
    if not schedule and not clean_sec and not clean_branch:
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

@router.post('/timetable')
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
    if clean_section in ("ALL", "ALL SECTIONS", "ALL SECTION"):
        clean_section = ""
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
            ON CONFLICT(day, hour, section) DO UPDATE SET
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

@router.delete('/timetable/{item_id}')
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

