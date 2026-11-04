"""
Modular Face Recognition Attendance System — FastAPI + SQLite
=============================================================
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from config import REPORTS_DIR

# Import routers
from routers import admin, students, attendance, timetable, roster, auth, teachers
from fastapi import Depends
from security import get_api_key

logger = logging.getLogger("attendance")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Scale asyncio worker thread pool to 64 threads for high concurrency CPU workloads (face matching & hashing)
    import asyncio
    import concurrent.futures
    try:
        loop = asyncio.get_running_loop()
        loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=64, thread_name_prefix="FastAPIWorker"))
        logger.info("Asyncio thread pool scaled to 64 workers for high concurrency.")
    except Exception as exc:
        logger.warning("Could not scale thread pool: %s", exc)

    await init_db()
    # Pre-load all enrolled students into the in-memory vectorized search matrix
    try:
        from database import get_db
        from services.face_engine import global_face_index
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT roll_no, name, face_encoding, device_id, branch_code, branch_name, section, year, class_roll_no, is_locked FROM students"
            )
            rows = await cursor.fetchall()
            global_face_index.load_all([dict(r) for r in rows])
            logger.info("Successfully loaded %d student profiles & vectors into in-memory index.", len(rows))
        finally:
            await db.close()
    except Exception as e:
        logger.error("Failed to pre-load face index: %s", e)
    yield

app = FastAPI(
    title="Face Recognition Attendance System",
    version="2.0.0",
    description="Modularized API for Face Registration & Attendance",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_and_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith(".html") or path.startswith("/api/auth"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "Modular Face Recognition Attendance System API is running.",
    }

# Include all modular routers
app.include_router(auth.router)
app.include_router(teachers.router)
app.include_router(admin.router, dependencies=[Depends(get_api_key)])
app.include_router(students.router, dependencies=[Depends(get_api_key)])
app.include_router(attendance.router, dependencies=[Depends(get_api_key)])
app.include_router(timetable.router, dependencies=[Depends(get_api_key)])
app.include_router(roster.router, dependencies=[Depends(get_api_key)])


# Serve the generated Excel reports
@app.get("/reports/{filename}")
async def get_report(filename: str):
    file_path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(file_path, filename=filename)

# Mount the static web dashboard
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSSIBLE_FRONTEND_PATHS = [
    os.path.join(os.path.dirname(BASE_DIR), "frontend"),
    os.path.join(BASE_DIR, "frontend"),
    r"D:\RFID\frontend",
]

for fpath in POSSIBLE_FRONTEND_PATHS:
    if os.path.isdir(fpath) and os.path.isfile(os.path.join(fpath, "index.html")):
        app.mount("/", StaticFiles(directory=fpath, html=True), name="frontend")
        break
