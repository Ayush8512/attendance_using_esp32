import aiosqlite
from config import DATABASE_PATH, TIMETABLE

async def get_db() -> aiosqlite.Connection:
    """Open (and return) a connection to the SQLite database."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    return db

async def init_db() -> None:
    """Create tables if they do not already exist."""
    db = await get_db()
    try:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                roll_no       TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                face_encoding TEXT NOT NULL,  -- JSON-serialised list of 128 floats
                is_locked     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT,
                updated_at    TEXT
            )
            """
        )
        # Safe column migration for existing DB
        for col in [
            "ALTER TABLE students ADD COLUMN is_locked INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE students ADD COLUMN created_at TEXT",
            "ALTER TABLE students ADD COLUMN updated_at TEXT",
            "ALTER TABLE students ADD COLUMN device_id TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN branch_code TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN branch_name TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN section TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN year INTEGER DEFAULT 1",
            "ALTER TABLE students ADD COLUMN class_roll_no TEXT DEFAULT ''",
        ]:
            try:
                await db.execute(col)
            except Exception:
                pass

        # College Master Roster table (All 7 Branches & 4 Years)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS college_roster (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                year            INTEGER NOT NULL,
                branch_code     TEXT NOT NULL,
                branch_name     TEXT NOT NULL,
                section         TEXT NOT NULL,
                semester        TEXT NOT NULL,
                class_roll_no   TEXT NOT NULL,
                primary_roll_no TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no     TEXT    NOT NULL,
                date        TEXT    NOT NULL,       -- YYYY-MM-DD
                time        TEXT    NOT NULL,       -- HH:MM:SS
                subject     TEXT    NOT NULL DEFAULT '',
                status      TEXT    NOT NULL DEFAULT 'Present',
                section     TEXT    NOT NULL DEFAULT '',
                branch_code TEXT    NOT NULL DEFAULT '',
                FOREIGN KEY (roll_no) REFERENCES students(roll_no)
            )
            """
        )
        for col in [
            "ALTER TABLE attendance ADD COLUMN subject TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE attendance ADD COLUMN section TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE attendance ADD COLUMN branch_code TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE attendance ADD COLUMN year INTEGER DEFAULT 0",
            "ALTER TABLE timetable ADD COLUMN section TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE timetable ADD COLUMN branch_code TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE timetable ADD COLUMN branch_name TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE timetable ADD COLUMN year INTEGER DEFAULT 0",
            "ALTER TABLE timetable ADD COLUMN end_hour INTEGER",
            "ALTER TABLE timetable ADD COLUMN end_minute INTEGER",
        ]:
            try:
                await db.execute(col)
            except Exception:
                pass

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS timetable (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                day                    TEXT    NOT NULL,
                hour                   INTEGER NOT NULL,
                start_minute           INTEGER NOT NULL DEFAULT 0,
                end_hour               INTEGER,
                end_minute             INTEGER,
                allowed_window_minutes INTEGER NOT NULL DEFAULT 10,
                subject                TEXT    NOT NULL,
                teacher_email          TEXT    NOT NULL,
                section                TEXT    NOT NULL DEFAULT '',
                branch_code            TEXT    NOT NULL DEFAULT '',
                branch_name            TEXT    NOT NULL DEFAULT '',
                year                   INTEGER DEFAULT 0,
                UNIQUE(day, hour, section)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS system_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        await db.execute(
            "INSERT OR IGNORE INTO system_settings (key, value) VALUES ('registration_open', '1')"
        )

        # Seed timetable table from default entries if empty
        cursor = await db.execute("SELECT COUNT(*) as count FROM timetable")
        row = await cursor.fetchone()
        if row and row["count"] == 0:
            for (day, hour), info in TIMETABLE.items():
                await db.execute(
                    """
                    INSERT OR IGNORE INTO timetable (day, hour, start_minute, allowed_window_minutes, subject, teacher_email)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        day,
                        hour,
                        info.get("start_minute", 0),
                        info.get("allowed_window_minutes", 10),
                        info["subject"],
                        info["teacher_email"],
                    ),
                )
        await db.commit()
    finally:
        await db.close()
