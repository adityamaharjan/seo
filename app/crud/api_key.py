"""Data-access functions for user-supplied provider API keys."""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKeyProvider, UserApiKey


async def get(
    db: AsyncSession, user_id: int, provider: ApiKeyProvider
) -> UserApiKey | None:
    res = await db.execute(
        select(UserApiKey).where(
            UserApiKey.user_id == user_id, UserApiKey.provider == provider
        )
    )
    return res.scalar_one_or_none()


async def list_for_user(db: AsyncSession, user_id: int) -> list[UserApiKey]:
    res = await db.execute(select(UserApiKey).where(UserApiKey.user_id == user_id))
    return list(res.scalars().all())


async def upsert(
    db: AsyncSession,
    *,
    user_id: int,
    provider: ApiKeyProvider,
    encrypted_key: str,
    key_hint: str,
) -> UserApiKey:
    row = await get(db, user_id, provider)
    if row is None:
        row = UserApiKey(user_id=user_id, provider=provider)
        db.add(row)
    row.encrypted_key = encrypted_key
    row.key_hint = key_hint
    # A freshly saved key starts clean; a stale rejection from the previous key
    # would otherwise keep showing in settings.
    row.last_error = None
    row.failure_count = 0
    await db.flush()
    return row


async def delete(db: AsyncSession, row: UserApiKey) -> None:
    await db.delete(row)
    await db.flush()


async def record_use(db: AsyncSession, row: UserApiKey) -> None:
    row.last_used_at = datetime.now(UTC)
    row.last_error = None
    row.failure_count = 0
    await db.flush()


async def record_failure(db: AsyncSession, row: UserApiKey, error: str) -> None:
    row.last_used_at = datetime.now(UTC)
    row.last_error = error[:255]
    row.failure_count += 1
    await db.flush()
