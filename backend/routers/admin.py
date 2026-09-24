from fastapi import APIRouter, Form, HTTPException, UploadFile, File
from typing import Optional
from datetime import datetime, date
import json
from database import get_db
from config import BRANCH_METADATA, FACE_MATCH_TOLERANCE
from schemas import AttendanceUpdate, AttendanceManualCreate, StudentProfileUpdate
from services.face_engine import extract_face_encoding, match_encoding, compute_match_confidence
from services.timetable_service import get_class_info_from_db, check_attendance_window
from services.report_service import generate_attendance_excel, send_email_with_attachment
import logging
logger = logging.getLogger('attendance')

router = APIRouter(tags=['admin'])

@router.post('/admin/students/{roll_no:path}/unlock')
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

@router.post('/admin/students/{roll_no:path}/lock')
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

@router.get('/admin/settings')
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

@router.post('/admin/settings/registration')
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

@router.post('/admin/students/{roll_no:path}/reset-device')
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


from pydantic import BaseModel
class ReportRequest(BaseModel):
    subject: str
    start_date: str
    end_date: str
    branch: str = ""
    section: str = ""
    action: str = "download"

@router.post('/admin/reports/generate')
async def generate_report_api(req: ReportRequest):
    """Generates a Cumulative Attendance Excel Report."""
    try:
        filepath, filename = await generate_attendance_excel(
            subject=req.subject,
            start_date=req.start_date,
            end_date=req.end_date,
            branch=req.branch if req.branch else None,
            section=req.section if req.section else None
        )
        if req.action == "email":
            # Just grab any first teacher's email from TIMETABLE for simplicity, or send to a default
            # In a real app, you'd pass the teacher email in the request
            from config import SENDER_EMAIL
            send_email_with_attachment(SENDER_EMAIL, f"Cumulative Report: {req.subject}", "Please find the requested attendance report attached.", filepath, filename)
            return {"status": "success", "message": "Report emailed successfully."}
        
        # Return download link
        return {"status": "success", "download_url": f"/reports/{filename}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
