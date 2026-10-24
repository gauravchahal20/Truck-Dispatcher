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


def validate_api_key_startup():
    """
    Validates API key configuration at application startup.
    In non-development environments (production, staging, etc.),
    refuses to start if an API key is not configured.
    """
    env = (getattr(settings, "environment", None) or os.getenv("ENVIRONMENT", "development")).strip().lower()
    if env not in ("development", "dev", "test", "testing"):
        key = get_configured_api_key()
        if not key or not key.strip():
            raise RuntimeError(
                f"Startup aborted: In '{env}' mode, API-key authentication must be configured. "
                "Please configure API_KEY, ADMIN_API_KEY, or GENLEAD_API_KEY."
            )


def require_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Enforces API key authentication on administrative and write endpoints:
    - If API key is configured in env:
        - Missing 'X-API-Key' -> 401 Unauthorized
        - Invalid 'X-API-Key' -> 403 Forbidden
        - Valid 'X-API-Key' -> Success
    - If no API key configured:
        - In non-dev environments -> 500 Server Misconfiguration
        - In dev/test environments -> Bypasses check for local development convenience.
    """
    configured_key = get_configured_api_key()
    env = (getattr(settings, "environment", None) or os.getenv("ENVIRONMENT", "development")).strip().lower()
    is_dev = env in ("development", "dev", "test", "testing")

    if not configured_key and not is_dev:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: API key authentication is mandatory in non-development environments."
        )

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

