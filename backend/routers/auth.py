from fastapi import APIRouter, Response, HTTPException, status, Request
from pydantic import BaseModel
from typing import Optional
from config import ADMIN_USERNAME, ADMIN_PASSWORD, API_KEY
from database import get_db
from security import verify_password

router = APIRouter(tags=['auth'])

class LoginData(BaseModel):
    username: str
    password: str

@router.post('/api/auth/login')
async def login(data: LoginData, response: Response):
    username_input = data.username.strip()
    password_input = data.password.strip()

    # 1. Check SQLite teachers database table by email or username
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, name, email, password_hash, department, role FROM teachers WHERE LOWER(email) = LOWER(?) OR LOWER(name) = LOWER(?)",
            (username_input, username_input)
        )
        teacher = await cursor.fetchone()
        if teacher and verify_password(password_input, teacher["password_hash"]):
            user_payload = {
                "id": teacher["id"],
                "name": teacher["name"],
                "email": teacher["email"],
                "role": teacher["role"],
                "department": teacher["department"] or "Faculty",
            }
            # Set cookies for session
            cookie_key = "admin_session" if teacher["role"] == "admin" else "teacher_session"
            response.set_cookie(
                key=cookie_key,
                value=API_KEY,
                httponly=False,
                samesite="lax",
                max_age=86400 * 30,
                path="/"
            )
            return {
                "status": "success",
                "message": f"Welcome back, {teacher['name']}!",
                "user": user_payload
            }
    finally:
        await db.close()

    # 2. Fallback check for system admin credentials (.env or default config)
    if username_input == ADMIN_USERNAME and password_input == ADMIN_PASSWORD:
        user_payload = {
            "id": 0,
            "name": "System Administrator",
            "email": "admin@college.edu",
            "role": "admin",
            "department": "Administration",
        }
        response.set_cookie(
            key="admin_session",
            value=API_KEY,
            httponly=False,
            samesite="lax",
            max_age=86400 * 30,
            path="/"
        )
        return {
            "status": "success",
            "message": "Logged in successfully as Administrator",
            "user": user_payload
        }

    raise HTTPException(status_code=401, detail="Invalid email/username or password.")

@router.get('/api/auth/me')
async def get_current_user_profile(request: Request):
    admin_cookie = request.cookies.get("admin_session")
    teacher_cookie = request.cookies.get("teacher_session")

    if admin_cookie == API_KEY:
        return {
            "status": "success",
            "user": {
                "id": 0,
                "name": "System Administrator",
                "email": "admin@college.edu",
                "role": "admin",
                "department": "Administration"
            }
        }
    
    if teacher_cookie:
        return {
            "status": "success",
            "user": {
                "id": 1,
                "name": "Faculty Member",
                "email": "teacher@college.edu",
                "role": "teacher",
                "department": "Faculty"
            }
        }

    return {"status": "unauthenticated", "user": None}

@router.post('/api/auth/logout')
async def logout(response: Response):
    response.delete_cookie("admin_session")
    response.delete_cookie("teacher_session")
    return {"status": "success", "message": "Logged out successfully"}

