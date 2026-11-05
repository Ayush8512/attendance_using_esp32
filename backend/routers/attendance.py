from fastapi import APIRouter, Form, HTTPException, UploadFile, File, BackgroundTasks
from typing import Optional
from datetime import datetime
from datetime import date
from utils import get_ist_now
import json
import os
from database import get_db, db_write_lock
from config import BRANCH_METADATA, FACE_MATCH_TOLERANCE
from utils import get_year_label
from schemas import AttendanceUpdate, AttendanceManualCreate, StudentProfileUpdate
from services.face_engine import extract_face_encoding, match_encoding, compute_match_confidence, global_face_index
from services.timetable_service import get_class_info_from_db, check_attendance_window, get_class_info, get_all_live_classes_from_db
from services.report_service import generate_attendance_excel, send_email_with_attachment
import logging
logger = logging.getLogger('attendance')

router = APIRouter(tags=['attendance'])

@router.post('/verify')
async def verify_attendance(
    background_tasks: BackgroundTasks,
    photo: UploadFile = File(..., description="Selfie photo for live verification"),
    roll_no: str | None = Form(None, description="Optional Roll Number for faster 1-to-1 matching"),
    device_id: str | None = Form(None, description="Optional Device UUID for hardware binding verification"),
    subject: str | None = Form(None, description="Optional target Subject/Class"),
    section: str | None = Form(None, description="Optional target Section")
):
    """
    Verify a student's identity and mark attendance.
    If roll_no is provided, it performs a 1-to-1 verification against the registered encoding.
    Enforces hardware device lock (Anti-Proxy) and strict time windows.
    """
    # ── 1. Strict Time Window Check (Server Time) ──
    now = get_ist_now()
    clean_roll = roll_no.strip().upper() if roll_no and roll_no.strip() else None
    student_section = None
    student_branch = None
    student_year = None

    if clean_roll:
        cached_stu = global_face_index.get_student(clean_roll)
        if cached_stu:
            student_section = cached_stu.get("section") or None
            student_branch = cached_stu.get("branch_code") or None
            student_year = cached_stu.get("year") or None
        else:
            db_s = await get_db()
            try:
                cur_s = await db_s.execute(
                    "SELECT section, branch_code, year FROM students WHERE roll_no = ?", (clean_roll,)
                )
                stu_row = await cur_s.fetchone()
                if stu_row:
                    student_section = stu_row["section"] or None
                    student_branch = stu_row["branch_code"] or None
                    student_year = stu_row["year"] or None
            finally:
                await db_s.close()

    class_info = await get_class_info_from_db(
        now,
        section=student_section,
        branch_code=student_branch,
        year=student_year,
    )

    if not class_info:
        cfg_info = get_class_info(now)
        if cfg_info and cfg_info.get("subject"):
            class_info = {
                "subject": cfg_info["subject"],
                "hour": cfg_info.get("hour", now.hour),
                "start_minute": cfg_info.get("start_minute", 0),
                "end_hour": cfg_info.get("end_hour"),
                "end_minute": cfg_info.get("end_minute"),
                "allowed_window_minutes": cfg_info.get("allowed_window_minutes", 20),
                "section": student_section or "",
                "branch_code": student_branch or "",
                "branch_name": "",
                "year": student_year or 0,
            }
        else:
            live_classes = await get_all_live_classes_from_db(now)
            if live_classes:
                class_info = live_classes[0]

    if not class_info:
        raise HTTPException(
            status_code=403,
            detail="No scheduled class is active right now for your section. Attendance can only be marked during scheduled class hours within the allowed time limit.",
        )

    # Strictly enforce the allowed window time limit
    is_allowed, time_err, window_end_str = check_attendance_window(class_info, now)
    if not is_allowed:
        raise HTTPException(
            status_code=403,
            detail=time_err,
        )

    try:
        photo_bytes = await photo.read()
        unknown_encoding = await extract_face_encoding(photo_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    current_subject = class_info.get("subject", "Class")

    # --- Load students for matching ---
    db = await get_db()
    try:
        # Ensure global vectorized face index is initialized
        if not global_face_index.is_loaded:
            init_cur = await db.execute("SELECT roll_no, name, face_encoding, device_id, branch_code, section, year FROM students")
            init_rows = await init_cur.fetchall()
            global_face_index.load_all([dict(r) for r in init_rows])

        if roll_no and roll_no.strip():
            # ── 1-to-1 High Speed In-Memory Verification (Anti-Proxy Architecture) ──
            clean_roll = roll_no.strip().upper()
            student = global_face_index.get_student(clean_roll)
            if not student:
                # Fallback to DB check
                cur_s = await db.execute("SELECT roll_no, name, face_encoding, device_id, branch_code, section, year FROM students WHERE roll_no = ?", (clean_roll,))
                row_s = await cur_s.fetchone()
                if not row_s:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Student with Roll Number '{clean_roll}' is not enrolled on this server.",
                    )
                student = dict(row_s)
                if isinstance(student["face_encoding"], str):
                    student["face_encoding"] = json.loads(student["face_encoding"])

            registered_dev = (student.get("device_id") or "").strip()
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

            known_encoding = student["face_encoding"]
            is_match, distance, confidence = match_encoding(known_encoding, unknown_encoding)
            logger.info(
                "1-to-1 Verification: roll=%s, name=%s, distance=%.4f (threshold=%.2f, confidence=%.1f%%)",
                clean_roll,
                student["name"],
                distance,
                FACE_MATCH_TOLERANCE,
                confidence,
            )
            
            if is_match:
                matched_roll_no = student["roll_no"]
                matched_name = student["name"]
                matched_section = student.get("section") or ""
                matched_branch = student.get("branch_code") or ""
                matched_year = student.get("year") or 1
                match_distance = distance
                match_confidence = confidence
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Face mismatch! (Distance: {distance:.4f} > {FACE_MATCH_TOLERANCE}). This does not appear to be {student['name']}. Proxy attendance blocked.",
                )
        else:
            # ── 1:N Ultra-Fast Vectorized Matrix Search (<0.5ms for 500+ students) ──
            matched_student, best_dist, best_conf = global_face_index.search_1toN(unknown_encoding, FACE_MATCH_TOLERANCE)
            if not matched_student:
                raise HTTPException(
                    status_code=404,
                    detail="Face not recognized among registered students. Please ensure good lighting and look directly at the camera.",
                )

            student = matched_student
            matched_roll_no = student["roll_no"]
            matched_name = student["name"]
            matched_section = student.get("section") or ""
            matched_branch = student.get("branch_code") or ""
            matched_year = student.get("year") or 1
            match_distance = best_dist
            match_confidence = best_conf

            registered_dev = (student.get("device_id") or "").strip()
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
            global_face_index.update_student_device(matched_roll_no, incoming_dev)

        # Dynamic Subject Resolution: ensure attendance is linked to the student's actual timetable class
        target_class_obj = None
        if subject and subject.strip():
            current_subject = subject.strip()
        else:
            resolved_class = await get_class_info_from_db(
                now,
                section=matched_section,
                branch_code=matched_branch,
                year=matched_year,
            )
            if resolved_class and resolved_class.get("subject"):
                current_subject = resolved_class["subject"]
                target_class_obj = resolved_class
            else:
                all_live = await get_all_live_classes_from_db(now)
                cand = None
                if all_live:
                    if matched_section:
                        cand = next((c for c in all_live if (c.get("section") or "").strip().upper() == matched_section.strip().upper()), None)
                    if not cand and matched_branch:
                        cand = next((c for c in all_live if (c.get("branch_code") or "").strip().upper() == matched_branch.strip().upper()), None)
                    if not cand and len(all_live) == 1:
                        cand = all_live[0]
                if cand and cand.get("subject"):
                    current_subject = cand["subject"]
                    target_class_obj = cand
                elif class_info and class_info.get("subject") and class_info.get("subject") not in ("General Attendance", "Academic Class"):
                    current_subject = class_info["subject"]
                    target_class_obj = class_info
                else:
                    cfg_match = get_class_info(now)
                    if cfg_match and cfg_match.get("subject"):
                        current_subject = cfg_match["subject"]
                    elif matched_branch and matched_branch in BRANCH_METADATA:
                        current_subject = f"{BRANCH_METADATA[matched_branch]['name']} Class"
                    elif matched_section:
                        current_subject = f"Section {matched_section} Class"
                    else:
                        current_subject = "Academic Session" 

        # Strict Attendance Window Enforcement:
        # If matched to a specific scheduled class, verify that the attendance window (e.g. 20 min) is still open!
        if target_class_obj:
            is_win_open, win_err_msg, _ = check_attendance_window(target_class_obj, now)
            if not is_win_open:
                raise HTTPException(
                    status_code=403,
                    detail=win_err_msg,
                )

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
        # Check if diagnostic photo cache is enabled for this student
        save_photo_diagnostic = bool(student.get("cache_flag") == 1)

        # Enqueue the write operation to background queue
        background_tasks.add_task(
            save_attendance_background,
            matched_roll_no, today, now_time_str, current_subject, matched_section, matched_branch, matched_year,
            photo_bytes if save_photo_diagnostic else None,
            save_photo_diagnostic
        )
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

@router.get('/attendance')
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
            SELECT a.id, a.roll_no, s.name, a.date, a.time, a.subject, a.status,
                   COALESCE(NULLIF(s.branch_code, ''), NULLIF(a.branch_code, ''), '') as branch_code,
                   COALESCE(NULLIF(s.section, ''), NULLIF(a.section, ''), '') as section,
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
            "id": row["id"],
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

@router.put('/attendance/{record_id:int}')
async def update_attendance_record(record_id: int, payload: AttendanceUpdate):
    """Update an individual attendance record (subject, status, date, time, section, branch)."""
    db = await get_db()
    try:
        cur = await db.execute("SELECT id, roll_no FROM attendance WHERE id = ?", (record_id,))
        rec = await cur.fetchone()
        if not rec:
            raise HTTPException(status_code=404, detail=f"Attendance record with ID {record_id} not found.")

        updates = []
        params = []
        if payload.status is not None and payload.status.strip():
            updates.append("status = ?")
            params.append(payload.status.strip())
        if payload.subject is not None and payload.subject.strip():
            updates.append("subject = ?")
            params.append(payload.subject.strip())
        if payload.date is not None and payload.date.strip():
            updates.append("date = ?")
            params.append(payload.date.strip())
        if payload.time is not None and payload.time.strip():
            updates.append("time = ?")
            params.append(payload.time.strip())
        if payload.section is not None:
            updates.append("section = ?")
            params.append(payload.section.strip().upper())
        if payload.branch_code is not None:
            updates.append("branch_code = ?")
            params.append(payload.branch_code.strip().upper())

        if updates:
            params.append(record_id)
            await db.execute(f"UPDATE attendance SET {', '.join(updates)} WHERE id = ?", params)
            await db.commit()

        return {"status": "success", "message": f"Attendance record #{record_id} updated successfully."}
    finally:
        await db.close()

@router.delete('/attendance/{record_id:int}')
async def delete_attendance_record(record_id: int):
    """Delete an individual attendance record by ID."""
    db = await get_db()
    try:
        cur = await db.execute("DELETE FROM attendance WHERE id = ?", (record_id,))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Attendance record with ID {record_id} not found.")
        return {"status": "success", "message": f"Attendance record #{record_id} deleted successfully."}
    finally:
        await db.close()

@router.post('/attendance/manual')
async def add_manual_attendance(payload: AttendanceManualCreate):
    """Manually add an attendance record for a student."""
    clean_roll = payload.roll_no.strip().upper()
    db = await get_db()
    try:
        # Check student exists in students table
        cur = await db.execute("SELECT roll_no, name, branch_code, section, year FROM students WHERE roll_no = ?", (clean_roll,))
        stu = await cur.fetchone()
        if not stu:
            # Check college roster
            r_cur = await db.execute("SELECT primary_roll_no, name, branch_code, section, year FROM college_roster WHERE primary_roll_no LIKE ? OR name LIKE ?", (f"%{clean_roll}%", f"%{clean_roll}%"))
            r_stu = await r_cur.fetchone()
            if not r_stu:
                raise HTTPException(status_code=404, detail=f"Student with roll number '{clean_roll}' not found in students or college roster.")
            student_name = r_stu["name"]
            sec = payload.section or r_stu["section"] or ""
            b_code = payload.branch_code or r_stu["branch_code"] or ""
            yr = r_stu["year"] or 1
        else:
            student_name = stu["name"]
            sec = payload.section or stu["section"] or ""
            b_code = payload.branch_code or stu["branch_code"] or ""
            yr = stu["year"] or 1

        rec_date = payload.date.strip() if payload.date else get_ist_now().strftime("%Y-%m-%d")
        rec_time = payload.time.strip() if payload.time else get_ist_now().strftime("%H:%M:%S")
        status_val = payload.status.strip() if payload.status else "Present"
        subj_val = payload.subject.strip()

        await db.execute(
            """
            INSERT OR IGNORE INTO attendance (roll_no, date, time, status, subject, section, branch_code, year)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (clean_roll, rec_date, rec_time, status_val, subj_val, sec, b_code, yr)
        )
        await db.commit()
        return {
            "status": "success",
            "message": f"Manual attendance marked for '{student_name}' ({clean_roll}) in {subj_val} as {status_val}.",
        }
    finally:
        await db.close()

async def save_attendance_background(
    roll_no: str,
    today: str,
    time_str: str,
    subject: str,
    section: str,
    branch: str,
    year: int,
    photo_bytes: Optional[bytes] = None,
    save_photo: bool = False,
):
    """Background task to safely save attendance to DB without blocking the API response."""
    async with db_write_lock:
        db = await get_db()
        try:
            await db.execute(
                """INSERT OR IGNORE INTO attendance (roll_no, date, time, subject, status, section, branch_code, year)
                   VALUES (?, ?, ?, ?, 'Present', ?, ?, ?)""",
                (roll_no, today, time_str, subject, section, branch, year)
            )
            await db.commit()
            logger.info("Attendance saved in background: roll=%s, date=%s, subject=%s", roll_no, today, subject)
        except Exception as e:
            logger.error("Background attendance save failed: %s", e)
        finally:
            await db.close()

    # Zero-load diagnostic cache: save photo asynchronously only when toggle is explicitly enabled
    if save_photo and photo_bytes:
        try:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", ".cache")
            os.makedirs(cache_dir, exist_ok=True)
            safe_time = time_str.replace(":", "-")
            safe_subj = "".join(c for c in subject if c.isalnum() or c in ("-", "_"))
            filename = f"{roll_no}_{today}_{safe_time}_{safe_subj}.jpg"
            file_path = os.path.join(cache_dir, filename)
            with open(file_path, "wb") as f:
                f.write(photo_bytes)
            logger.info("Diagnostic photo snapshot saved: %s", filename)
        except Exception as err:
            logger.warning("Failed to save diagnostic photo: %s", err)


