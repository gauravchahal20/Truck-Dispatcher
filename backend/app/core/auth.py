import os
import secrets
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_configured_api_key() -> str | None:
    """Reads configured API key from environment variables or settings."""
    return (
        os.getenv("API_KEY") or
        os.getenv("ADMIN_API_KEY") or
        os.getenv("GENLEAD_API_KEY") or
        getattr(settings, "api_key", None)
    )


def require_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Enforces API key authentication on administrative and write endpoints:
    - If API key is configured in env:
        - Missing 'X-API-Key' -> 401 Unauthorized
        - Invalid 'X-API-Key' -> 403 Forbidden
        - Valid 'X-API-Key' -> Success
    - If no API key configured:
        - Bypasses check for local development convenience.
    """
    configured_key = get_configured_api_key()

    if configured_key:
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: 'X-API-Key' header missing."
            )
        if not secrets.compare_digest(api_key.strip(), configured_key.strip()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Invalid API key provided."
            )
        return api_key

    return "unauthenticated_dev"
