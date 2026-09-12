"""Data-access functions for quotas."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.quota import Quota


async def get_by_user_id(
    db: AsyncSession, user_id: int, *, for_update: bool = False
) -> Quota | None:
    """Load a user's quota row.

    ``for_update`` takes a row lock so that a read-modify-write of the usage
    counters is atomic against concurrent requests. It is a no-op on SQLite
    (used by the tests), which serializes writes anyway.
    """
    stmt = select(Quota).where(Quota.user_id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def create(db: AsyncSession, user_id: int) -> Quota:
    quota = Quota(
        user_id=user_id,
        daily_limit=settings.FREE_DAILY_LIMIT,
        monthly_limit=settings.FREE_MONTHLY_LIMIT,
    )
    db.add(quota)
    await db.flush()
    return quota
