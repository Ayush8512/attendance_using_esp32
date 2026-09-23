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
