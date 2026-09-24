from fastapi import Security, HTTPException, status, Cookie, Request
from fastapi.security.api_key import APIKeyHeader
from config import API_KEY
from typing import Optional

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(
    request: Request,
    api_key_header: Optional[str] = Security(api_key_header)
):
    # Check Header First
    if api_key_header == API_KEY:
        return api_key_header
        
    # Check Cookie (for Web Dashboard)
    admin_session = request.cookies.get("admin_session")
    if admin_session == API_KEY:
        return admin_session
        
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate API KEY or Session"
    )
