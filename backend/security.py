from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from config import API_KEY

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == API_KEY:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate API KEY"
    )
