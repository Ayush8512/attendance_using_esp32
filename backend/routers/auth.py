from fastapi import APIRouter, Form, Response, HTTPException, status
from pydantic import BaseModel
from config import ADMIN_USERNAME, ADMIN_PASSWORD, API_KEY

router = APIRouter(tags=['auth'])

class LoginData(BaseModel):
    username: str
    password: str

@router.post('/api/auth/login')
async def login(data: LoginData, response: Response):
    if data.username == ADMIN_USERNAME and data.password == ADMIN_PASSWORD:
        # Set HttpOnly cookie with the API key so the frontend acts as authenticated
        response.set_cookie(
            key="admin_session",
            value=API_KEY,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30, path="/" # 30 days
        )
        return {"status": "success", "message": "Logged in successfully"}
    
    raise HTTPException(status_code=401, detail="Invalid username or password")

@router.post('/api/auth/logout')
async def logout(response: Response):
    response.delete_cookie("admin_session")
    return {"status": "success", "message": "Logged out successfully"}
