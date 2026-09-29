from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import get_db
from security import hash_password, get_api_key

router = APIRouter(prefix="/api/teachers", tags=["teachers"], dependencies=[Depends(get_api_key)])

class TeacherCreate(BaseModel):
    name: str
    email: str
    password: str
    department: Optional[str] = "Faculty"
    role: Optional[str] = "teacher"

class TeacherOut(BaseModel):
    id: int
    name: str
    email: str
    department: Optional[str]
    role: str
    created_at: Optional[str]

@router.get("", response_model=List[TeacherOut])
async def list_teachers():
    """Retrieve list of all registered teacher accounts."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, name, email, department, role, created_at FROM teachers ORDER BY role DESC, name ASC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()

@router.post("", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
async def create_teacher(payload: TeacherCreate):
    """Register a new teacher account."""
    name = payload.name.strip()
    email = payload.email.strip().lower()
    password = payload.password.strip()
    department = payload.department.strip() if payload.department else "Faculty"
    role = payload.role.strip().lower() if payload.role else "teacher"

    if not name or not email or not password:
        raise HTTPException(status_code=400, detail="Name, Email, and Password are required.")

    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters long.")

    db = await get_db()
    try:
        cur = await db.execute("SELECT id FROM teachers WHERE LOWER(email) = LOWER(?)", (email,))
        existing = await cur.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail=f"A teacher with email '{email}' already exists.")

        hashed_pwd = hash_password(password)
        now_iso = datetime.now().isoformat()

        cursor = await db.execute(
            """
            INSERT INTO teachers (name, email, password_hash, department, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, email, hashed_pwd, department, role, now_iso)
        )
        await db.commit()
        new_id = cursor.lastrowid

        return {
            "id": new_id,
            "name": name,
            "email": email,
            "department": department,
            "role": role,
            "created_at": now_iso
        }
    finally:
        await db.close()

@router.delete("/{teacher_id}")
async def delete_teacher(teacher_id: int):
    """Delete a teacher account by ID."""
    db = await get_db()
    try:
        cur = await db.execute("SELECT id, name FROM teachers WHERE id = ?", (teacher_id,))
        teacher = await cur.fetchone()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found.")

        await db.execute("DELETE FROM teachers WHERE id = ?", (teacher_id,))
        await db.commit()
        return {"status": "success", "message": f"Teacher '{teacher['name']}' deleted successfully."}
    finally:
        await db.close()
