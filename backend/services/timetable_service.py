import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from database import get_db
from config import TIMETABLE, ATTENDANCE_WINDOW_MINUTES

logger = logging.getLogger("attendance.timetable_service")

def get_class_info(dt: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    if dt is None:
        dt = datetime.now()
    day_name = dt.strftime("%A")
    hour = dt.hour
    return TIMETABLE.get((day_name, hour))

async def get_class_info_from_db(
    dt: Optional[datetime] = None,
    section: Optional[str] = None,
    branch_code: Optional[str] = None,
    year: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if dt is None:
        dt = datetime.now()
    day_name = dt.strftime("%A")
    hour = dt.hour

    try:
        db = await get_db()
        try:
            current_minute = dt.minute
            current_total = hour * 60 + current_minute

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

            if section and section.strip():
                clean_sec = section.strip().upper()
                cur = await db.execute(
                    f"""
                    SELECT day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email, 
                           COALESCE(section, '') as section, COALESCE(branch_code, '') as branch_code, 
                           COALESCE(branch_name, '') as branch_name, COALESCE(year, 0) as year
                    FROM timetable
                    WHERE day = ? AND {active_where()} AND UPPER(section) = ?
                    ORDER BY hour DESC, start_minute DESC
                    LIMIT 1
                    """,
                    (day_name, current_total, current_total, clean_sec),
                )
                row = await cur.fetchone()
                if row:
                    return dict(row)

            if branch_code and branch_code.strip():
                clean_br = branch_code.strip().upper()
                yr_clause = "AND (year = ? OR year = 0)" if year else ""
                yr_params = [year] if year else []
                cur = await db.execute(
                    f"""
                    SELECT day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email,
                           COALESCE(section, '') as section, COALESCE(branch_code, '') as branch_code, 
                           COALESCE(branch_name, '') as branch_name, COALESCE(year, 0) as year
                    FROM timetable
                    WHERE day = ? AND {active_where()} AND UPPER(branch_code) = ? {yr_clause}
                      AND (section IS NULL OR section = '' OR UPPER(section) = 'ALL' OR UPPER(section) = 'ALL SECTIONS')
                    ORDER BY hour DESC, start_minute DESC
                    LIMIT 1
                    """,
                    [day_name, current_total, current_total, clean_br] + yr_params,
                )
                row = await cur.fetchone()
                if row:
                    return dict(row)

            clean_br = branch_code.strip().upper() if branch_code and branch_code.strip() else ""
            cursor = await db.execute(
                f"""
                SELECT day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email,
                       COALESCE(section, '') as section, COALESCE(branch_code, '') as branch_code, 
                       COALESCE(branch_name, '') as branch_name, COALESCE(year, 0) as year
                FROM timetable
                WHERE day = ? AND {active_where()}
                  AND (section IS NULL OR section = '' OR UPPER(section) = 'ALL' OR UPPER(section) = 'ALL SECTIONS')
                  AND (branch_code IS NULL OR branch_code = '' OR UPPER(branch_code) = 'ALL' OR UPPER(branch_code) = 'ALL BRANCHES' OR UPPER(branch_code) = ?)
                ORDER BY hour DESC, start_minute DESC
                LIMIT 1
                """,
                (day_name, current_total, current_total, clean_br),
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
        finally:
            await db.close()
    except Exception as exc:
        logger.debug("Could not query timetable table: %s", exc)

    if section or branch_code:
        return None

    return get_class_info(dt)


def check_attendance_window(class_info: Dict[str, Any], dt: Optional[datetime] = None) -> Tuple[bool, str, str]:
    if dt is None:
        dt = datetime.now()

    start_hour = class_info.get("hour", dt.hour)
    start_minute = class_info.get("start_minute", 0)
    end_hour = class_info.get("end_hour")
    end_minute = class_info.get("end_minute")
    allowed_minutes = class_info.get("allowed_window_minutes", ATTENDANCE_WINDOW_MINUTES)

    class_start = dt.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    
    if end_hour is not None and end_minute is not None:
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
