"""Quota enforcement: free tier of 5 analyses per user per day.

The daily counter resets on the first request of a new UTC day; a monthly
counter is tracked alongside for reporting. Call :func:`consume` exactly once
per successful analysis request.
"""
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import QuotaExceededError
from app.crud import quota as quota_crud
from app.models.quota import Quota


def _apply_resets(quota: Quota, today: date, now: datetime) -> None:
    if quota.day_reset_date != today:
        quota.used_today = 0
        quota.day_reset_date = today
    if quota.month_reset_date is None or (
        quota.month_reset_date.year,
        quota.month_reset_date.month,
    ) != (now.year, now.month):
        quota.used_this_month = 0
        quota.month_reset_date = now


def _seconds_until_tomorrow(now: datetime) -> int:
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int((tomorrow - now).total_seconds())


async def consume(db: AsyncSession, user_id: int) -> Quota:
    """Reset counters as needed, enforce the daily cap, then increment usage.

    The row is locked for the read-modify-write. Without the lock two
    concurrent submissions both read the same ``used_today`` and both write the
    same increment, letting a user exceed the daily limit.
    """
    quota = await quota_crud.get_by_user_id(db, user_id, for_update=True)
    if quota is None:
        quota = await quota_crud.create(db, user_id)

    now = datetime.now(UTC)
    today = now.date()
    _apply_resets(quota, today, now)

    if quota.used_today >= quota.daily_limit:
        retry_after = _seconds_until_tomorrow(now)
        raise QuotaExceededError(
            f"Daily free limit of {quota.daily_limit} analyses reached.",
            details={
                "daily_limit": quota.daily_limit,
                "used_today": quota.used_today,
                "resets_at": (today + timedelta(days=1)).isoformat() + "T00:00:00Z",
            },
            headers={"Retry-After": str(retry_after)},
        )

    quota.used_today += 1
    quota.used_this_month += 1
    await db.flush()
    return quota


async def refund(db: AsyncSession, user_id: int) -> None:
    """Give back one unit after an analysis failed before doing any work.

    A failed fetch should not cost the user part of their daily allowance. The
    counters are floored at zero so a refund that crosses a daily reset cannot
    push them negative.
    """
    quota = await quota_crud.get_by_user_id(db, user_id, for_update=True)
    if quota is None:
        return
    quota.used_today = max(0, quota.used_today - 1)
    quota.used_this_month = max(0, quota.used_this_month - 1)
    await db.flush()


async def get_status(db: AsyncSession, user_id: int) -> Quota:
    quota = await quota_crud.get_by_user_id(db, user_id)
    if quota is None:
        quota = await quota_crud.create(db, user_id)
    now = datetime.now(UTC)
    _apply_resets(quota, now.date(), now)
    await db.flush()
    return quota
