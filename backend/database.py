import os
import aiosqlite
import logging
from config import DATABASE_PATH, TIMETABLE

logger = logging.getLogger("attendance.db")


async def get_db() -> aiosqlite.Connection:
    """Open and return a SQLite database connection."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    """Create SQLite tables if they do not already exist."""
    db = await get_db()
    try:
        await db.execute("PRAGMA journal_mode=WAL")

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                roll_no       TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                face_encoding TEXT NOT NULL,
                is_locked     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT,
                updated_at    TEXT,
                device_id     TEXT DEFAULT '',
                branch_code   TEXT DEFAULT '',
                branch_name   TEXT DEFAULT '',
                section       TEXT DEFAULT '',
                year          INTEGER DEFAULT 1,
                class_roll_no TEXT DEFAULT ''
            )
            """
        )

        # Safe column migrations (ignore if already exists)
        for col_sql in [
            "ALTER TABLE students ADD COLUMN device_id TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN branch_code TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN branch_name TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN section TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN year INTEGER DEFAULT 1",
            "ALTER TABLE students ADD COLUMN class_roll_no TEXT DEFAULT ''",
            "ALTER TABLE students ADD COLUMN is_locked INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE students ADD COLUMN created_at TEXT",
            "ALTER TABLE students ADD COLUMN updated_at TEXT",
        ]:
            try:
                await db.execute(col_sql)
            except Exception:
                pass

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
                date        TEXT    NOT NULL,
                time        TEXT    NOT NULL,
                subject     TEXT    NOT NULL DEFAULT '',
                status      TEXT    NOT NULL DEFAULT 'Present',
                section     TEXT    NOT NULL DEFAULT '',
                branch_code TEXT    NOT NULL DEFAULT '',
                year        INTEGER DEFAULT 1,
                UNIQUE(roll_no, date, subject)
            )
            """
        )

        for col_sql in [
            "ALTER TABLE attendance ADD COLUMN year INTEGER DEFAULT 1",
        ]:
            try:
                await db.execute(col_sql)
            except Exception:
                pass

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS timetable (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                day                    TEXT NOT NULL,
                hour                   INTEGER NOT NULL,
                start_minute           INTEGER NOT NULL DEFAULT 0,
                end_hour               INTEGER,
                end_minute             INTEGER,
                allowed_window_minutes INTEGER DEFAULT 15,
                subject                TEXT NOT NULL,
                teacher_email          TEXT NOT NULL DEFAULT '',
                section                TEXT DEFAULT '',
                branch_code            TEXT DEFAULT '',
                branch_name            TEXT DEFAULT '',
                year                   INTEGER DEFAULT 1,
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

        # Indexes for fast lookups
        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_attendance_roll_no ON attendance(roll_no)",
            "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date)",
            "CREATE INDEX IF NOT EXISTS idx_attendance_section ON attendance(section, branch_code)",
            "CREATE INDEX IF NOT EXISTS idx_students_device_id ON students(device_id)",
            "CREATE INDEX IF NOT EXISTS idx_roster_search ON college_roster(branch_code, section, year)",
        ]:
            try:
                await db.execute(idx)
            except Exception:
                pass

        await db.commit()
        logger.info("SQLite database initialized at: %s", DATABASE_PATH)

    finally:
        await db.close()
