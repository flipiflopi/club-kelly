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
