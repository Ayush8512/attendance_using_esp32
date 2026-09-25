import logging
from datetime import datetime, timedelta
from utils import get_ist_now
from typing import Optional, Dict, Any, Tuple

from database import get_db
from config import TIMETABLE, ATTENDANCE_WINDOW_MINUTES

logger = logging.getLogger("attendance.timetable_service")

def get_class_info(dt: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    if dt is None:
        dt = get_ist_now()
    day_name = dt.strftime("%A")
    hour = dt.hour
    info = TIMETABLE.get((day_name, hour))
    if info:
        c_dict = dict(info)
        c_dict["day"] = day_name
        c_dict["hour"] = hour
        return format_class_timings(c_dict)
    return None

def format_class_timings(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to attach human-readable 12-hour and 24-hour time ranges to class dictionaries."""
    h = row_dict.get("hour", 0) or 0
    sm = row_dict.get("start_minute", 0) or 0
    eh = row_dict.get("end_hour")
    em = row_dict.get("end_minute")
    wm = row_dict.get("allowed_window_minutes", ATTENDANCE_WINDOW_MINUTES) or ATTENDANCE_WINDOW_MINUTES

    if eh is not None and em is not None:
        time_24h = f"{h:02d}:{sm:02d} - {eh:02d}:{em:02d}"
        st_obj = datetime.strptime(f"{h:02d}:{sm:02d}", "%H:%M")
        et_obj = datetime.strptime(f"{eh:02d}:{em:02d}", "%H:%M")
        time_12h = f"{st_obj.strftime('%I:%M %p')} - {et_obj.strftime('%I:%M %p')}"
    else:
        time_24h = f"{h:02d}:{sm:02d} - {h:02d}:59"
        st_obj = datetime.strptime(f"{h:02d}:{sm:02d}", "%H:%M")
        et_obj = datetime.strptime(f"{h:02d}:59", "%H:%M")
        time_12h = f"{st_obj.strftime('%I:%M %p')} - {et_obj.strftime('%I:%M %p')}"

    we_total = h * 60 + sm + wm
    we_h = (we_total // 60) % 24
    we_m = we_total % 60
    we_obj = datetime.strptime(f"{we_h:02d}:{we_m:02d}", "%H:%M")
    window_12h = we_obj.strftime("%I:%M %p")

    row_dict["time_label"] = time_24h
    row_dict["timing_12h"] = time_12h
    row_dict["window_end_time"] = window_12h
    row_dict["attendance_window_label"] = f"{st_obj.strftime('%I:%M %p')} - {window_12h} ({wm} min window)"
    return row_dict

async def get_all_live_classes_from_db(dt: Optional[datetime] = None) -> list[Dict[str, Any]]:
    """Retrieve all classes currently live across all sections and branches."""
    if dt is None:
        dt = get_ist_now()
    day_name = dt.strftime("%A")
    hour = dt.hour
    current_minute = dt.minute
    current_total = hour * 60 + current_minute

    live_classes = []
    try:
        db = await get_db()
        try:
            cursor = await db.execute(
                """
                SELECT id, day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email,
                       COALESCE(section, '') as section, COALESCE(branch_code, '') as branch_code, 
                       COALESCE(branch_name, '') as branch_name, COALESCE(year, 0) as year
                FROM timetable
                WHERE day = ?
                  AND (hour * 60 + COALESCE(start_minute, 0)) <= ?
                  AND (
                      CASE
                          WHEN end_hour IS NOT NULL AND end_minute IS NOT NULL
                          THEN end_hour * 60 + end_minute
                          ELSE hour * 60 + COALESCE(start_minute, 0) + COALESCE(allowed_window_minutes, 15)
                      END
                  ) > ?
                ORDER BY section, hour, start_minute
                """,
                (day_name, current_total, current_total),
            )
            rows = await cursor.fetchall()
            today_iso = dt.strftime("%Y-%m-%d")

            for r in rows:
                c_dict = format_class_timings(dict(r))
                is_open, msg, win_end = check_attendance_window(c_dict, dt)
                c_dict["window_status"] = {
                    "is_open": is_open,
                    "window_end": win_end,
                    "message": "Window open for attendance" if is_open else msg,
                }
                sec_filter = c_dict.get("section", "")
                if sec_filter and sec_filter not in ("ALL", "ALL SECTIONS"):
                    att_cur = await db.execute(
                        "SELECT COUNT(*) as cnt FROM attendance WHERE date = ? AND subject = ? AND UPPER(section) = ?",
                        (today_iso, c_dict["subject"], sec_filter.upper()),
                    )
                else:
                    att_cur = await db.execute(
                        "SELECT COUNT(*) as cnt FROM attendance WHERE date = ? AND subject = ?",
                        (today_iso, c_dict["subject"]),
                    )
                cnt_row = await att_cur.fetchone()
                c_dict["present_count"] = cnt_row["cnt"] if cnt_row else 0
                live_classes.append(c_dict)
        finally:
            await db.close()
    except Exception as exc:
        logger.error("Error in get_all_live_classes_from_db: %s", exc)

    return live_classes

async def get_class_info_from_db(
    dt: Optional[datetime] = None,
    section: Optional[str] = None,
    branch_code: Optional[str] = None,
    year: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if dt is None:
        dt = get_ist_now()
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
                    return format_class_timings(dict(row))

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
                    return format_class_timings(dict(row))

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
                return format_class_timings(dict(row))
        finally:
            await db.close()
    except Exception as exc:
        logger.debug("Could not query timetable table: %s", exc)

    if section or branch_code:
        return None

    return get_class_info(dt)


def check_attendance_window(class_info: Dict[str, Any], dt: Optional[datetime] = None) -> Tuple[bool, str, str]:
    if dt is None:
        dt = get_ist_now()

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
