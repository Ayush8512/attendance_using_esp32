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
            send_email_with_attachment(SENDER_EMAIL, f"Cumulative Report: {req.subject}", "Please find the requested attendance report attached.", filepath)
            return {"status": "success", "message": "Report emailed successfully."}
        
        # Return download link
        return {"status": "success", "download_url": f"/reports/{filename}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/admin/end-class')
@router.post('/end_class')
async def end_class_endpoint(
    subject: str = Form(...),
    teacher_email: str | None = Form(None),
    section: str | None = Form(None),
    branch_code: str | None = Form(None),
    start_date: str | None = Form(None),
    end_date: str | None = Form(None),
):
    """End a live class session, generate a cumulative register Excel spreadsheet, and email it to the teacher."""
    try:
        from utils import get_ist_now
        now = get_ist_now()
        today = now.strftime("%Y-%m-%d")
        clean_subj = subject.strip()
        clean_sec = section.strip().upper() if section and section.strip() not in ("ALL", "ALL SECTIONS") else None
        clean_br = branch_code.strip().upper() if branch_code and branch_code.strip() not in ("ALL", "ALL BRANCHES") else None

        # Cumulative register: default to 1st of current month up to today (consolidates all lectures into a single date-wise register)
        clean_start = start_date.strip() if start_date and start_date.strip() else today[:7] + "-01"
        clean_end = end_date.strip() if end_date and end_date.strip() else today

        filepath, filename = await generate_attendance_excel(
            subject=clean_subj,
            start_date=clean_start,
            end_date=clean_end,
            section=clean_sec,
            branch=clean_br,
        )

        email_status = "Excel sheet generated."
        target_email = teacher_email.strip() if teacher_email and teacher_email.strip() else None
        if not target_email:
            from config import SENDER_EMAIL
            target_email = SENDER_EMAIL

        if target_email:
            try:
                date_range_label = today if clean_start == clean_end else f"{clean_start} to {clean_end}"
                subject_line = f"Official Attendance Register: {clean_subj} ({date_range_label})"
                body_plain = f"""Dear Faculty Member,

Please find attached the official cumulative attendance register for your subject '{clean_subj}'.

Lecture Details:
- Subject: {clean_subj}
- Register Period: {date_range_label}
- Section: {clean_sec or 'All Sections'}
- Branch: {clean_br or 'All Branches'}
- Spreadsheet: {filename} (.xlsx)

The attached Excel spreadsheet contains the complete verified attendance records with biometric timestamps.

Sincerely,
Academic Administration
Institute of Engineering and Rural Technology (IERT), Prayagraj
"""
                body_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f1f5f9; color: #1e293b; margin: 0; padding: 24px; }}
        .card {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #cbd5e1; overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,0.08); }}
        .header {{ background: #0f172a; color: #ffffff; padding: 24px 28px; border-bottom: 3px solid #38bdf8; }}
        .header h2 {{ margin: 0 0 6px 0; font-size: 20px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px; }}
        .header p {{ margin: 0; font-size: 13px; color: #94a3b8; font-weight: 500; }}
        .content {{ padding: 28px; font-size: 14px; line-height: 1.6; color: #334155; }}
        .content p {{ margin: 0 0 14px 0; }}
        .details-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; }}
        .details-table td {{ padding: 10px 16px; border-bottom: 1px solid #e2e8f0; font-size: 13px; }}
        .details-table tr:last-child td {{ border-bottom: none; }}
        .details-table td.label {{ color: #64748b; font-weight: 600; width: 35%; }}
        .details-table td.value {{ color: #0f172a; font-weight: 700; }}
        .footer {{ background: #f8fafc; padding: 18px 28px; font-size: 11px; color: #64748b; text-align: center; border-top: 1px solid #e2e8f0; line-height: 1.5; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <h2>Institute of Engineering and Rural Technology</h2>
            <p>Smart Classroom Attendance Portal &bull; Prayagraj</p>
        </div>
        <div class="content">
            <p>Dear Faculty Member,</p>
            <p>Please find attached the official attendance register for your lecture session conducted on <strong>{today}</strong>.</p>
            <table class="details-table">
                <tr><td class="label">Subject</td><td class="value">{clean_subj}</td></tr>
                <tr><td class="label">Date</td><td class="value">{today}</td></tr>
                <tr><td class="label">Section</td><td class="value">{clean_sec or 'All Sections'}</td></tr>
                <tr><td class="label">Branch</td><td class="value">{clean_br or 'All Branches'}</td></tr>
                <tr><td class="label">Spreadsheet</td><td class="value">{filename} (.xlsx)</td></tr>
            </table>
            <p style="font-size: 13px; color: #64748b; margin-top: 16px;">The attached file contains the complete student roster with attendance status (Present / Absent) and biometric timestamps.</p>
        </div>
        <div class="footer">
            This is an automated notification generated by the IERT Smart Attendance System.<br>
            &copy; Institute of Engineering and Rural Technology, Prayagraj, UP, India.
        </div>
    </div>
</body>
</html>"""

                send_email_with_attachment(
                    target_email,
                    subject_line,
                    body_plain,
                    filepath,
                    html_body=body_html,
                )
                email_status = f"Official Excel attendance report emailed to {target_email}."
            except Exception as mail_err:
                logger.warning("Could not email sheet to %s: %s", target_email, mail_err)
                email_status = f"Excel sheet generated, but email delivery skipped/failed: {mail_err}"

        return {
            "status": "success",
            "message": email_status,
            "download_url": f"/reports/{filename}",
            "filename": filename,
        }
    except Exception as e:
        logger.error("End class failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

