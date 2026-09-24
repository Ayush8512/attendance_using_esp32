
import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from datetime import timezone, timedelta
    ZoneInfo = None

def get_ist_now() -> datetime.datetime:
    """Returns the current time in Asia/Kolkata timezone, safe for cloud deployments."""
    if ZoneInfo is not None:
        return datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    # Fallback if zoneinfo is somehow missing (e.g. older python)
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
def get_year_label(yr: int | None = None, sec: str | None = None) -> str:
    """Helper to convert year number or section code into standard label (e.g. 1st Year)."""
    if yr and yr in (1, 2, 3, 4):
        suffixes = {1: "1st Year", 2: "2nd Year", 3: "3rd Year", 4: "4th Year"}
        return suffixes.get(yr, f"Year {yr}")
    if sec and len(sec) >= 2 and sec[1] in ("1", "2", "3", "4"):
        y = int(sec[1])
        suffixes = {1: "1st Year", 2: "2nd Year", 3: "3rd Year", 4: "4th Year"}
        return suffixes.get(y, f"Year {y}")
    return "N/A"
