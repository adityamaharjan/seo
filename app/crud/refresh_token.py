"""Data-access functions for refresh tokens."""
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


async def revoke_all_for_user(db: AsyncSession, user_id: int) -> int:
    """Revoke every live token for a user. Returns how many were revoked.

    Used when a password changes and when an administrator disables or
    demotes an account, so an already-issued refresh token cannot be traded
    for fresh access after the fact.
    """
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await db.flush()
    return cast(CursorResult, result).rowcount or 0


async def count_active_for_user(db: AsyncSession, user_id: int) -> int:
    from sqlalchemy import func

    return int(
        await db.scalar(
            select(func.count())
            .select_from(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        )
        or 0
    )
