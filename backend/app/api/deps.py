import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db


def get_db_session(db: Session = Depends(get_db)) -> Session:
    return db


def verify_webhook_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Optional API key guard for n8n webhook endpoints.
    If WEBHOOK_API_KEY is empty, all requests are allowed (internal network assumed).
    """
    settings = get_settings()
    if not settings.webhook_api_key:
        return
    if x_api_key != settings.webhook_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def verify_admin_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Mandatory API key guard for the admin API.
    Uses ADMIN_API_KEY, falling back to WEBHOOK_API_KEY. Unlike webhooks, the admin
    API is never left open: with no key configured every request is refused.
    """
    settings = get_settings()
    expected = settings.admin_api_key or settings.webhook_api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API disabled: set ADMIN_API_KEY",
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
