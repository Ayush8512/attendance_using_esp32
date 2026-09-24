from fastapi import APIRouter, Form, HTTPException, UploadFile, File
from typing import Optional
from datetime import datetime, date
import json
from database import get_db
from config import BRANCH_METADATA, FACE_MATCH_TOLERANCE
from schemas import AttendanceUpdate, AttendanceManualCreate, StudentProfileUpdate
from services.face_engine import extract_face_encoding, match_encoding, compute_match_confidence, global_face_index
from services.timetable_service import get_class_info_from_db, check_attendance_window
from services.report_service import generate_attendance_excel, send_email_with_attachment
import logging
logger = logging.getLogger('attendance')

router = APIRouter(tags=['students'])

@router.post('/register')
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
            photo_bytes = await photo.read()
            encoding = await extract_face_encoding(photo_bytes, is_registration=True)
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

@router.post('/students/login')
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

@router.get('/students')
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

@router.get('/students/{roll_no}/analytics')
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

@router.get('/students/{roll_no}')
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

@router.put('/students/{roll_no}')
async def update_student_profile(roll_no: str, payload: StudentProfileUpdate):
    """Update student profile (name, branch, section, year, class roll) and sync attendance records."""
    clean_roll = roll_no.strip().upper()
    db = await get_db()
    try:
        cur = await db.execute("SELECT roll_no, name FROM students WHERE roll_no = ?", (clean_roll,))
        student = await cur.fetchone()
        if not student:
            raise HTTPException(status_code=404, detail=f"Student with roll number '{clean_roll}' not found.")

        updates = []
        params = []
        if payload.name is not None and payload.name.strip():
            updates.append("name = ?")
            params.append(payload.name.strip())
        if payload.branch_code is not None and payload.branch_code.strip():
            b_code = payload.branch_code.strip().upper()
            b_name = BRANCH_METADATA.get(b_code, {}).get("name", "")
            updates.append("branch_code = ?")
            params.append(b_code)
            updates.append("branch_name = ?")
            params.append(b_name)
        if payload.section is not None:
            sec_val = payload.section.strip().upper()
            updates.append("section = ?")
            params.append(sec_val)
        if payload.year is not None:
            updates.append("year = ?")
            params.append(payload.year)
        if payload.class_roll_no is not None:
            updates.append("class_roll_no = ?")
            params.append(payload.class_roll_no.strip())

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            params.append(clean_roll)
            await db.execute(f"UPDATE students SET {', '.join(updates)} WHERE roll_no = ?", params)

            # Sync existing attendance records with updated branch, section, year
            att_updates = []
            att_params = []
            if payload.branch_code is not None and payload.branch_code.strip():
                att_updates.append("branch_code = ?")
                att_params.append(payload.branch_code.strip().upper())
            if payload.section is not None:
                att_updates.append("section = ?")
                att_params.append(payload.section.strip().upper())
            if payload.year is not None:
                att_updates.append("year = ?")
                att_params.append(payload.year)

            if att_updates:
                att_params.append(clean_roll)
                await db.execute(f"UPDATE attendance SET {', '.join(att_updates)} WHERE roll_no = ?", att_params)

            await db.commit()

        return {"status": "success", "message": f"Student '{clean_roll}' profile updated successfully."}
    finally:
        await db.close()

@router.delete('/students/{roll_no}')
async def delete_student(roll_no: str):
    """Delete a registered student and their attendance records."""
    clean_roll = roll_no.strip().upper()
    db = await get_db()
    try:
        cur = await db.execute("DELETE FROM students WHERE roll_no = ?", (clean_roll,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Student with roll number '{clean_roll}' not found.")
        
        await db.execute("DELETE FROM attendance WHERE roll_no = ?", (clean_roll,))
        await db.commit()
        global_face_index.is_loaded = False
    finally:
        await db.close()
    return {"status": "success", "message": f"Student '{clean_roll}' deleted successfully."}



