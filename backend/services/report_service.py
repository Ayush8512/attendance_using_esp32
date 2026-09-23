import os
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd

from database import get_db
from config import REPORTS_DIR, BRANCH_METADATA, SENDER_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
from utils import get_year_label

logger = logging.getLogger("attendance.reports")

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


def send_email_with_attachment(
    to_email: str,
    subject_line: str,
    body: str,
    attachment_path: str,
) -> None:
    """
    Send an email with a single ``.xlsx`` attachment via SMTP (TLS).
    """
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject_line

    msg.attach(MIMEText(body, "plain"))

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
