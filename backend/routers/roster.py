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

router = APIRouter(tags=['roster'])

@router.get('/roster/branches')
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

@router.get('/roster/students')
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

@router.get('/roster/lookup/{roll_no:path}')
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

@router.get('/roster/stats')
async def get_roster_stats():
    """Get high-level registration stats across all 7 branches & 4 years."""
    db = await get_db()
    try:
        tot_roster_cur = await db.execute("SELECT COUNT(*) FROM college_roster")
        total_roster = list((await tot_roster_cur.fetchone()).values())[0]

        tot_reg_cur = await db.execute("SELECT COUNT(*) FROM students")
        total_registered = list((await tot_reg_cur.fetchone()).values())[0]

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

