import logging
import time
from datetime import datetime, timedelta
from utils import get_ist_now
from typing import Optional, Dict, Any, Tuple

from database import get_db
from config import TIMETABLE, ATTENDANCE_WINDOW_MINUTES

logger = logging.getLogger("attendance.timetable_service")

# In-memory high-throughput TTL caches (5 seconds TTL) to serve concurrent student requests with zero DB lag
_live_classes_cache: Dict[str, Any] = {"time": 0.0, "data": []}
_class_info_cache: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}

def clear_timetable_cache() -> None:
    """Clear in-memory timetable caches when schedule is updated."""
    global _live_classes_cache, _class_info_cache
    _live_classes_cache = {"time": 0.0, "data": []}
    _class_info_cache.clear()

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
    """Retrieve all classes currently live across all sections and branches (with 5s in-memory TTL cache)."""
    global _live_classes_cache
    now_ts = time.time()
    if dt is None and (now_ts - _live_classes_cache["time"]) < 5.0 and _live_classes_cache["data"]:
        return [dict(c) for c in _live_classes_cache["data"]]

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
                          ELSE hour * 60 + COALESCE(start_minute, 0) + 55
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

    if dt is None:
        _live_classes_cache = {"time": now_ts, "data": [dict(c) for c in live_classes]}
    return live_classes

async def get_class_info_from_db(
    dt: Optional[datetime] = None,
    section: Optional[str] = None,
    branch_code: Optional[str] = None,
    year: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if dt is None:
        dt = get_ist_now()
    
    clean_sec = (section or "").strip().upper()
    clean_br = (branch_code or "").strip().upper()
    now_ts = time.time()
    cache_key = f"{dt.strftime('%A')}_{dt.hour}_{dt.minute // 2}_{clean_sec}_{clean_br}_{year or 0}"
    cached = _class_info_cache.get(cache_key)
    if cached and (now_ts - cached[0]) < 5.0:
        return dict(cached[1]) if cached[1] is not None else None

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
                            ELSE hour * 60 + COALESCE(start_minute, 0) + 55
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

    # If no exact minute match, check for recent scheduled class today for this section/branch
    try:
        db_rec = await get_db()
        try:
            if section and section.strip():
                cur_rec = await db_rec.execute(
                    """
                    SELECT day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email,
                           COALESCE(section, '') as section, COALESCE(branch_code, '') as branch_code, 
                           COALESCE(branch_name, '') as branch_name, COALESCE(year, 0) as year
                    FROM timetable
                    WHERE day = ? AND UPPER(section) = ?
                      AND (hour * 60 + COALESCE(start_minute, 0)) <= ?
                      AND (hour * 60 + COALESCE(start_minute, 0)) >= (? - 120)
                    ORDER BY hour DESC, start_minute DESC LIMIT 1
                    """,
                    (day_name, clean_sec, current_total, current_total),
                )
                row_rec = await cur_rec.fetchone()
                if row_rec:
                    return format_class_timings(dict(row_rec))
            elif branch_code and branch_code.strip():
                cur_rec = await db_rec.execute(
                    """
                    SELECT day, hour, start_minute, end_hour, end_minute, allowed_window_minutes, subject, teacher_email,
                           COALESCE(section, '') as section, COALESCE(branch_code, '') as branch_code, 
                           COALESCE(branch_name, '') as branch_name, COALESCE(year, 0) as year
                    FROM timetable
                    WHERE day = ? AND UPPER(branch_code) = ?
                      AND (hour * 60 + COALESCE(start_minute, 0)) <= ?
                      AND (hour * 60 + COALESCE(start_minute, 0)) >= (? - 120)
                    ORDER BY hour DESC, start_minute DESC LIMIT 1
                    """,
                    (day_name, clean_br, current_total, current_total),
                )
                row_rec = await cur_rec.fetchone()
                if row_rec:
                    return format_class_timings(dict(row_rec))
        finally:
            await db_rec.close()
    except Exception as exc:
        logger.debug("Recent class lookup fallback error: %s", exc)

    # Fallback to standard academic curriculum timetable from config.py
    cfg_class = get_class_info(dt)
    if cfg_class:
        if section:
            cfg_class["section"] = section
        if branch_code:
            cfg_class["branch_code"] = branch_code
        return cfg_class

    return None


def check_attendance_window(class_info: Dict[str, Any], dt: Optional[datetime] = None) -> Tuple[bool, str, str]:
    if dt is None:
        dt = get_ist_now()

    start_hour = class_info.get("hour", dt.hour)
    start_minute = class_info.get("start_minute", 0)
    end_hour = class_info.get("end_hour")
    end_minute = class_info.get("end_minute")
    allowed_minutes = class_info.get("allowed_window_minutes", ATTENDANCE_WINDOW_MINUTES)
    if allowed_minutes is None or allowed_minutes <= 0:
        allowed_minutes = ATTENDANCE_WINDOW_MINUTES

    class_start = dt.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    
    # Strict window: Attendance is only allowed for `allowed_minutes` from class start
    window_end = class_start + timedelta(minutes=allowed_minutes)

    # If the class has a defined end time, the window cannot exceed the class end time
    if end_hour is not None and end_minute is not None:
        class_end = dt.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        if class_end < class_start:
            class_end += timedelta(days=1)
        if window_end > class_end:
            window_end = class_end
        
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
