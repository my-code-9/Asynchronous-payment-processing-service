import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

api_key_scheme = APIKeyHeader(
    name="X-API-Key",
    description="API Key",
)


async def verify_api_key(
    api_key: str = Security(api_key_scheme),
):
    if not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )