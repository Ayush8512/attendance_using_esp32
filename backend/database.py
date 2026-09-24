import os
import asyncpg
import logging
from config import SUPABASE_URL, DATABASE_PATH, TIMETABLE

logger = logging.getLogger("attendance.db")

_pool = None

class AsyncpgCursor:
    def __init__(self, records, rowcount):
        self._records = records
        self.rowcount = rowcount
        
    async def fetchall(self):
        return self._records
        
    async def fetchone(self):
        return self._records[0] if self._records else None

class AsyncpgDBWrapper:
    def __init__(self, con):
        self.con = con
        self.row_factory = None
        
    def _convert_query(self, query: str) -> str:
        # Replaces '?' with '$1', '$2', etc. for Postgres
        parts = query.split('?')
        if len(parts) == 1:
            return query
        new_query = parts[0]
        for i in range(1, len(parts)):
            new_query += f"${i}" + parts[i]
        return new_query

    async def execute(self, query: str, parameters=None):
        pg_query = self._convert_query(query)
        params = parameters or ()
        
        q_upper = pg_query.strip().upper()
        is_select_or_returning = q_upper.startswith("SELECT") or q_upper.startswith("PRAGMA") or "RETURNING" in q_upper
        
        try:
            if is_select_or_returning:
                # PRAGMA doesn't exist in Postgres, catch and ignore
                if q_upper.startswith("PRAGMA"):
                    return AsyncpgCursor([], 0)
                
                records = await self.con.fetch(pg_query, *params)
                return AsyncpgCursor(records, len(records))
            else:
                status = await self.con.execute(pg_query, *params)
                # status is like "UPDATE 1" or "INSERT 0 1"
                try:
                    rowcount = int(status.split()[-1])
                except:
                    rowcount = 0
                return AsyncpgCursor([], rowcount)
        except Exception as e:
            logger.error(f"DB Error on query: {pg_query} with params {params} -> {e}")
            raise e

    async def commit(self):
        pass # asyncpg handles autocommit by default outside of explicit transactions

    async def close(self):
        # We release the connection back to the pool
        global _pool
        if _pool and self.con:
            await _pool.release(self.con)
            self.con = None

async def init_pool():
    global _pool
    if not _pool:
        # Add ssl=require to connection string if not present
        url = SUPABASE_URL
        if "?" not in url:
            url += "?sslmode=require"
        _pool = await asyncpg.create_pool(url, min_size=1, max_size=10)
    return _pool

async def get_db():
    """Open (and return) a wrapped asyncpg connection."""
    pool = await init_pool()
    con = await pool.acquire()
    return AsyncpgDBWrapper(con)

async def init_db() -> None:
    """Create Postgres tables if they do not already exist."""
    db = await get_db()
    try:
        # Postgres uses SERIAL for auto-incrementing integers
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                roll_no       TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                face_encoding TEXT NOT NULL,
                is_locked     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT,
                updated_at    TEXT
            )
            """
        )
        
        # Postgres column migration (ignore if exists)
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

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS college_roster (
                id              SERIAL PRIMARY KEY,
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
                id          SERIAL PRIMARY KEY,
                roll_no     TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                time        TEXT    NOT NULL,
                subject     TEXT    NOT NULL DEFAULT '',
                status      TEXT    NOT NULL DEFAULT 'Present',
                section     TEXT    NOT NULL DEFAULT '',
                branch_code TEXT    NOT NULL DEFAULT '',
                UNIQUE(roll_no, date, subject)
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

        # Ensure Timetable settings exist
        for tt_id, tt_info in TIMETABLE.items():
            try:
                await db.execute(
                    "INSERT INTO system_settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO NOTHING",
                    (f"tt_{tt_id}", tt_info["start_time"])
                )
            except Exception:
                pass
                
        # --- Add Database Indexes for O(1) Data Retrieval ---
        try: await db.execute("CREATE INDEX IF NOT EXISTS idx_attendance_roll_no ON attendance(roll_no)")
        except: pass
        try: await db.execute("CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date)")
        except: pass
        try: await db.execute("CREATE INDEX IF NOT EXISTS idx_attendance_section ON attendance(section, branch_code)")
        except: pass
        try: await db.execute("CREATE INDEX IF NOT EXISTS idx_students_device_id ON students(device_id)")
        except: pass
        try: await db.execute("CREATE INDEX IF NOT EXISTS idx_roster_search ON college_roster(branch_code, section, year)")
        except: pass

    finally:
        await db.close()
