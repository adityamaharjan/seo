"""Authentication business logic: signup, login, refresh rotation, logout."""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.crud import quota as quota_crud
from app.crud import user as user_crud
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPair


async def signup(
    db: AsyncSession, *, username: str, email: str, password: str
) -> User:
    if await user_crud.get_existing(db, email, username):
        raise ConflictError("A user with that email or username already exists.")
    user = await user_crud.create(
        db,
        username=username,
        email=email,
        hashed_password=security.hash_password(password),
    )
    await quota_crud.create(db, user.id)
    await db.commit()
    await db.refresh(user)
    return user


async def _issue_tokens(db: AsyncSession, user: User) -> TokenPair:
    access = security.create_access_token(user.id, user.role.value)
    refresh, jti, expires_at = security.create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            jti=jti,
            token_hash=security.hash_token(refresh),
            expires_at=expires_at,
        )
    )
    await db.commit()
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def login(db: AsyncSession, *, email: str, password: str) -> TokenPair:
    user = await user_crud.get_by_email(db, email)
    if not user or not security.verify_password(password, user.hashed_password):
        raise AuthenticationError("Invalid email or password.")
    if not user.is_active:
        raise AuthenticationError("This account is disabled.")
    return await _issue_tokens(db, user)


async def refresh(db: AsyncSession, refresh_token: str) -> TokenPair:
    payload = security.decode_token(refresh_token)
    if not payload or payload.get("type") != security.REFRESH:
        raise AuthenticationError("Invalid refresh token.")

    jti = payload.get("jti")
    res = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    stored = res.scalar_one_or_none()
    if not stored:
        raise AuthenticationError("Refresh token is invalid or expired.")
    # Some backends (e.g. SQLite) return naive datetimes; treat them as UTC.
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if (
        stored.revoked
        or stored.token_hash != security.hash_token(refresh_token)
        or expires_at < datetime.now(UTC)
    ):
        raise AuthenticationError("Refresh token is invalid or expired.")

    # Rotation: revoke the presented token before issuing a new pair.
    stored.revoked = True
    user = await user_crud.get_by_id(db, int(payload["sub"]))
    if not user or not user.is_active:
        raise AuthenticationError("Account not found or disabled.")
    return await _issue_tokens(db, user)


async def logout(db: AsyncSession, refresh_token: str) -> None:
    payload = security.decode_token(refresh_token)
    if not payload:
        return
    res = await db.execute(
        select(RefreshToken).where(RefreshToken.jti == payload.get("jti"))
    )
    stored = res.scalar_one_or_none()
    if stored:
        stored.revoked = True
        await db.commit()
