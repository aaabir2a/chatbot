"""Password hashing (bcrypt) and JWT issue/verify for org dashboard auth."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(org_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": org_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def decode_access_token(token: str) -> str:
    """Return org_id (sub) or raise jwt exceptions."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    return payload["sub"]
