"""Password hashing and JWT token utilities.

Passwords are pre-hashed with SHA-256 before bcrypt so that secrets longer
than bcrypt's 72-byte limit are fully mixed in (a pattern carried over from
the prototype). We call the ``bcrypt`` library directly instead of passlib,
which fails to read the version of bcrypt 5.x.
"""
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

ACCESS = "access"
REFRESH = "refresh"


# --- Passwords ---

def _prehash(password: str) -> bytes:
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    digest = _prehash(password)
    return bcrypt.hashpw(digest, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT ---

def _encode(subject: str, token_type: str, expires_delta: timedelta, **extra: Any) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex,
        **extra,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    return _encode(
        str(user_id),
        ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        role=role,
    )


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    """Return (token, jti, expires_at)."""
    expires_at = datetime.now(UTC) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    jti = uuid.uuid4().hex
    token = _encode(
        str(user_id),
        REFRESH,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        jti=jti,
    )
    return token, jti, expires_at


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None


def hash_token(token: str) -> str:
    """Opaque hash for storing refresh tokens at rest."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)
