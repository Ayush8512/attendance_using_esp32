import hashlib
import os
from fastapi import Security, HTTPException, status, Cookie, Request
from fastapi.security.api_key import APIKeyHeader
from config import API_KEY
from typing import Optional

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

VALID_API_KEYS = {
    API_KEY,
    "iert_sas_secure_key_2026",
    "default_secret_api_key_for_dev_only"
}

def hash_password(password: str, salt: bytes = None) -> str:
    """Hash password using PBKDF2 HMAC SHA-256."""
    if salt is None:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ':' + key.hex()

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against PBKDF2 hash string."""
    try:
        if not hashed_password or ':' not in hashed_password:
            return False
        salt_hex, key_hex = hashed_password.split(':')
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return key == expected_key
    except Exception:
        return False

async def get_api_key(
    request: Request,
    api_key_header: Optional[str] = Security(api_key_header)
):
    # Check Header First
    if api_key_header and api_key_header in VALID_API_KEYS:
        return api_key_header
        
    # Check Cookie (for Web Dashboard)
    admin_session = request.cookies.get("admin_session")
    if admin_session and (admin_session in VALID_API_KEYS or admin_session == API_KEY):
        return admin_session

    teacher_session = request.cookies.get("teacher_session")
    if teacher_session:
        return teacher_session
        
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate API KEY or Session"
    )
