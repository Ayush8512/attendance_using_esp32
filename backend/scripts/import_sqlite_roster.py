"""
Quick SQLite Roster Importer
Runs the load_iert_roster.py data directly into the local SQLite DB.
"""
import sys
import os
import sqlite3
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'attendance.db')

BRANCH_NAMES = {
    "A": "Computer Science & Engineering",
    "B": "Electronics Engineering",
    "C": "Industrial & Production Engineering",
    "D": "Mechanical Engineering",
    "E": "Instrumentation & Control Engineering",
    "F": "Electrical Engineering",
    "G": "Civil Engineering",
}

# Import the roster data from the main script
import importlib.util
spec = importlib.util.spec_from_file_location(
    "iert_roster",
    os.path.join(os.path.dirname(__file__), 'load_iert_roster.py')
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

RAW_ROSTER = mod.RAW_ROSTER
print(f"Total entries to import: {len(RAW_ROSTER)}")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

inserted = 0
skipped = 0

for entry in RAW_ROSTER:
    try:
        year, branch_code, section, class_roll_int, semester, aktu_suffix, class_roll_no, name = entry
        branch_name = BRANCH_NAMES.get(branch_code, 'Engineering')
        primary_roll_no = str(aktu_suffix).strip()
        if not primary_roll_no or primary_roll_no.isdigit():
            primary_roll_no = f"24{year:02d}100{branch_code}00{int(class_roll_int):04d}"

        c.execute(
            """INSERT OR IGNORE INTO college_roster 
               (year, branch_code, branch_name, section, semester, class_roll_no, primary_roll_no, name)
               VALUES (?,?,?,?,?,?,?,?)""",
            (year, branch_code, branch_name, section, str(semester), str(class_roll_no), primary_roll_no, name)
        )
        if c.rowcount > 0:
            inserted += 1
        else:
            skipped += 1
    except Exception as e:
        print(f"  Error: {e} | entry={entry}")
        skipped += 1

conn.commit()

# Verify
c.execute("SELECT COUNT(*) FROM college_roster")
total = c.fetchone()[0]
conn.close()

print(f"Done! Inserted: {inserted} | Skipped: {skipped} | Total in DB: {total}")
