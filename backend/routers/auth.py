import asyncio
import random
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Response, HTTPException, status, Request
from pydantic import BaseModel
from typing import Optional
from config import ADMIN_USERNAME, ADMIN_PASSWORD, API_KEY
from database import get_db, db_write_lock
from security import verify_password, hash_password
from utils import send_email_otp

router = APIRouter(tags=['auth'])

class LoginData(BaseModel):
    username: str
    password: str

async def create_web_session(user_payload: dict, response: Response) -> str:
    """Creates a secure persistent session token in SQLite and sets 1-year browser cookies."""
    session_token = secrets.token_hex(32)
    expires_at = (datetime.now() + timedelta(days=365)).isoformat()
    db = await get_db()
    try:
        async with db_write_lock:
            await db.execute(
                """INSERT INTO web_sessions (token, user_id, name, email, role, department, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_token,
                    user_payload["id"],
                    user_payload["name"],
                    user_payload["email"],
                    user_payload["role"],
                    user_payload["department"],
                    datetime.now().isoformat(),
                    expires_at
                )
            )
            await db.commit()
    finally:
        await db.close()

    # 1-Year persistent session cookies
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=False,
        samesite="lax",
        max_age=86400 * 365,
        path="/"
    )
    cookie_key = "admin_session" if user_payload["role"] == "admin" else "teacher_session"
    response.set_cookie(
        key=cookie_key,
        value=session_token,
        httponly=False,
        samesite="lax",
        max_age=86400 * 365,
        path="/"
    )
    return session_token

@router.post('/api/auth/login')
async def login(data: LoginData, response: Response):
    username_input = data.username.strip()
    password_input = data.password.strip()

    # 1. Check SQLite teachers database table by email, name, or first name
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, name, email, password_hash, department, role 
               FROM teachers 
               WHERE email = ? COLLATE NOCASE 
                  OR name = ? COLLATE NOCASE
                  OR LOWER(name) LIKE LOWER(?) || '%'
                  OR LOWER(email) LIKE LOWER(?) || '@%'""",
            (username_input, username_input, username_input, username_input)
        )
        candidates = await cursor.fetchall()
        for cand in candidates:
            if await asyncio.to_thread(verify_password, password_input, cand["password_hash"]):
                user_payload = {
                    "id": cand["id"],
                    "name": cand["name"],
                    "email": cand["email"],
                    "role": cand["role"],
                    "department": cand["department"] or "Faculty",
                }
                session_token = await create_web_session(user_payload, response)
                return {
                    "status": "success",
                    "message": f"Welcome back, {cand['name']}!",
                    "user": user_payload,
                    "token": session_token
                }
    finally:
        await db.close()

    # 2. Check for Super Administrator credentials exclusively from .env (no hardcoded passwords)
    clean_admin_env = (ADMIN_USERNAME or "").strip().lower()
    if clean_admin_env and ADMIN_PASSWORD and (username_input.lower() == clean_admin_env) and (password_input == ADMIN_PASSWORD):
        user_payload = {
            "id": 0,
            "name": "Ayush Pandey (Super Administrator)",
            "email": "ayushpandey111223@gmail.com",
            "role": "admin",
            "department": "System Administration",
        }
        session_token = await create_web_session(user_payload, response)
        return {
            "status": "success",
            "message": "Logged in successfully as Administrator",
            "user": user_payload,
            "token": session_token
        }

    raise HTTPException(status_code=401, detail="Invalid email/username or password.")

@router.get('/api/auth/me')
async def get_current_user_profile(request: Request, response: Response):
    """Returns active user profile if session token exists and is valid in SQLite web_sessions."""
    token = request.cookies.get("session_token") or request.cookies.get("admin_session") or request.cookies.get("teacher_session")
    if token:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT user_id, name, email, role, department, expires_at FROM web_sessions WHERE token = ?",
                (token,)
            )
            row = await cursor.fetchone()
            if row:
                if row["expires_at"] > datetime.now().isoformat():
                    return {
                        "status": "success",
                        "user": {
                            "id": row["user_id"],
                            "name": row["name"],
                            "email": row["email"],
                            "role": row["role"],
                            "department": row["department"]
                        }
                    }
                else:
                    async with db_write_lock:
                        await db.execute("DELETE FROM web_sessions WHERE token = ?", (token,))
                        await db.commit()
        except Exception:
            pass
        finally:
            await db.close()

    # Clear invalid / stale cookies
    response.delete_cookie("session_token", path="/")
    response.delete_cookie("admin_session", path="/")
    response.delete_cookie("teacher_session", path="/")
    return {"status": "unauthenticated", "user": None}

class SendOTPData(BaseModel):
    email: str

class VerifyOTPData(BaseModel):
    email: str
    otp: str
    new_password: str

class ForgotPasswordData(BaseModel):
    email: str
    new_password: str
    otp: Optional[str] = None

@router.post('/api/auth/send-otp')
async def send_otp(data: SendOTPData):
    """Generate 6-digit OTP, store in database password_otps, and send via email/SMTP."""
    email_input = data.email.strip().lower()
    if not email_input:
        raise HTTPException(status_code=400, detail="Email address is required.")

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, name, email FROM teachers WHERE LOWER(email) = LOWER(?)",
            (email_input,)
        )
        teacher = await cursor.fetchone()
        if not teacher:
            raise HTTPException(status_code=404, detail=f"No faculty account found with email '{email_input}'.")

        # Generate 6-digit numeric OTP code
        otp_code = str(random.randint(100000, 999999))
        now = datetime.now()
        expires_at = (now + timedelta(minutes=10)).isoformat()
        created_at = now.isoformat()

        # Invalidate previous unused OTPs for this email
        await db.execute(
            "UPDATE password_otps SET used = 1 WHERE LOWER(email) = LOWER(?) AND used = 0",
            (email_input,)
        )

        # Insert new OTP record into database
        await db.execute(
            """
            INSERT INTO password_otps (email, otp, expires_at, created_at, used)
            VALUES (?, ?, ?, ?, 0)
            """,
            (email_input, otp_code, expires_at, created_at)
        )
        await db.commit()

        # Dispatch email or log fallback
        send_email_otp(teacher["email"], otp_code, teacher["name"])

        return {
            "status": "success",
            "message": f"OTP sent to '{teacher['email']}'. Valid for 10 minutes."
        }
    finally:
        await db.close()

@router.post('/api/auth/verify-otp')
async def verify_otp(data: VerifyOTPData):
    """Verify OTP code from database and update teacher password hash."""
    email_input = data.email.strip().lower()
    otp_input = data.otp.strip()
    new_pwd = data.new_password.strip()

    if not email_input or not otp_input or not new_pwd:
        raise HTTPException(status_code=400, detail="Email, OTP code, and new password are required.")

    if len(new_pwd) < 4:
        raise HTTPException(status_code=400, detail="New password must be at least 4 characters long.")

    db = await get_db()
    try:
        cursor = await db.execute("SELECT id, name FROM teachers WHERE LOWER(email) = LOWER(?)", (email_input,))
        teacher = await cursor.fetchone()
        if not teacher:
            raise HTTPException(status_code=404, detail=f"No faculty account found with email '{email_input}'.")

        # Query active OTP
        cur_otp = await db.execute(
            """
            SELECT id, expires_at, used FROM password_otps
            WHERE LOWER(email) = LOWER(?) AND otp = ? AND used = 0
            ORDER BY id DESC LIMIT 1
            """,
            (email_input, otp_input)
        )
        otp_row = await cur_otp.fetchone()
        if not otp_row:
            raise HTTPException(status_code=400, detail="Invalid OTP code. Please check your email and try again.")

        expires_at_dt = datetime.fromisoformat(otp_row["expires_at"])
        if datetime.now() > expires_at_dt:
            raise HTTPException(status_code=400, detail="OTP code has expired. Please click 'Send OTP' to get a new code.")

        # Mark OTP as used
        await db.execute("UPDATE password_otps SET used = 1 WHERE id = ?", (otp_row["id"],))

        # Update teacher password hash
        hashed = hash_password(new_pwd)
        await db.execute("UPDATE teachers SET password_hash = ? WHERE id = ?", (hashed, teacher["id"]))
        await db.commit()

        return {
            "status": "success",
            "message": f"Password reset successful for {teacher['name']}. You can now log in with your new password."
        }
    finally:
        await db.close()

@router.post('/api/auth/forgot-password')
async def forgot_password(data: ForgotPasswordData):
    """Secure OTP-backed password reset endpoint."""
    if not data.otp or not data.otp.strip():
        raise HTTPException(
            status_code=400,
            detail="A valid 6-digit OTP code is required to reset password. Please click 'Send OTP' first."
        )
    return await verify_otp(VerifyOTPData(email=data.email, otp=data.otp, new_password=data.new_password))

@router.post('/api/auth/logout')
async def logout(request: Request, response: Response):
    """Logs out the current browser session."""
    token = request.cookies.get("session_token") or request.cookies.get("admin_session") or request.cookies.get("teacher_session")
    if token:
        db = await get_db()
        try:
            async with db_write_lock:
                await db.execute("DELETE FROM web_sessions WHERE token = ?", (token,))
                await db.commit()
        except Exception:
            pass
        finally:
            await db.close()

    response.delete_cookie("session_token", path="/")
    response.delete_cookie("admin_session", path="/")
    response.delete_cookie("teacher_session", path="/")
    return {"status": "success", "message": "Logged out successfully"}

@router.post('/api/auth/logout-all')
async def logout_all_users(response: Response):
    """Invalidates all active web sessions across all devices and browsers."""
    db = await get_db()
    try:
        async with db_write_lock:
            await db.execute("DELETE FROM web_sessions")
            await db.commit()
    finally:
        await db.close()

    response.delete_cookie("session_token", path="/")
    response.delete_cookie("admin_session", path="/")
    response.delete_cookie("teacher_session", path="/")
    return {"status": "success", "message": "All active sessions have been invalidated."}
