"""API key generation/verification and FastAPI auth dependencies."""
import hashlib
import logging
import secrets

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db.base import get_db
from app.db.models import ApiKey, Chatbot, CrmKey, Organization
from app.services.security import decode_access_token

logger = logging.getLogger(__name__)

KEY_PREFIX = "sk"


def generate_api_key(kind: str = KEY_PREFIX) -> tuple[str, str, str]:
    """Return (full_key, prefix, key_hash).

    full_key is shown to the caller exactly once and never persisted.
    `kind` sets the human prefix, e.g. "sk" for chatbot keys, "crm" for CRM keys.
    """
    secret = secrets.token_urlsafe(32)
    full_key = f"{kind}_{secret}"
    prefix = full_key[:12]
    key_hash = hash_key(full_key)
    return full_key, prefix, key_hash


def hash_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()


def require_api_key(
    request: Request,
    db: Session = Depends(get_db),
) -> Chatbot:
    """Resolve the chatbot scoped to the API key in the request header.

    Raises 401 if the key is missing, unknown, or revoked. The resolved
    Chatbot is the *only* tenant scope downstream code may act within.
    """
    raw = request.headers.get(settings.api_key_header)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing API key header '{settings.api_key_header}'.",
        )

    key_hash = hash_key(raw)
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == key_hash, ApiKey.revoked.is_(False))
        .first()
    )
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key."
        )

    # Track usage (best-effort; don't fail the request if this write hiccups).
    from datetime import datetime, timezone

    api_key.last_used_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:
        db.rollback()

    chatbot = db.get(Chatbot, api_key.chatbot_id)
    if chatbot is None:
        raise HTTPException(status_code=401, detail="API key has no associated chatbot.")
    return chatbot


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Guard management endpoints. No-op unless ADMIN_TOKEN is configured."""
    if not settings.admin_token:
        return
    if x_admin_token != settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin token."
        )


def require_org(
    request: Request,
    db: Session = Depends(get_db),
) -> Organization:
    """Resolve the logged-in Organization from a Bearer JWT (dashboard auth)."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    token = header[len("Bearer "):].strip()
    try:
        org_id = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token."
        )
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown org.")
    return org


def owned_chatbot(db: Session, org: Organization, chatbot_id: str) -> Chatbot:
    """Fetch a chatbot, enforcing that it belongs to the calling org."""
    chatbot = db.get(Chatbot, chatbot_id)
    if chatbot is None or chatbot.org_id != org.id:
        raise HTTPException(status_code=404, detail="Chatbot not found.")
    return chatbot


def require_crm_key(
    request: Request,
    db: Session = Depends(get_db),
) -> Organization:
    """Resolve the Organization from a CRM API key (header X-CRM-Key).

    No login needed — a valid CRM key grants read access to that org's data.
    """
    raw = request.headers.get("X-CRM-Key")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing CRM API key header 'X-CRM-Key'.",
        )
    crm_key = (
        db.query(CrmKey)
        .filter(CrmKey.key_hash == hash_key(raw), CrmKey.revoked.is_(False))
        .first()
    )
    if crm_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked CRM key."
        )
    from datetime import datetime, timezone

    crm_key.last_used_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:
        db.rollback()

    org = db.get(Organization, crm_key.org_id)
    if org is None:
        raise HTTPException(status_code=401, detail="CRM key has no associated org.")
    return org
