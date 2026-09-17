"""Data-access functions for SEO reports."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report, ReportStatus


async def create_pending(
    db: AsyncSession,
    *,
    user_id: int,
    url: str,
    target_keywords: list[str] | None = None,
    used_psi: bool = False,
) -> Report:
    report = Report(
        user_id=user_id,
        url=url,
        status=ReportStatus.pending,
        target_keywords=target_keywords or None,
        used_psi=used_psi,
    )
    db.add(report)
    await db.flush()
    return report


async def get(db: AsyncSession, report_id: int) -> Report | None:
    return await db.get(Report, report_id)


async def get_for_user(
    db: AsyncSession, report_id: int, user_id: int
) -> Report | None:
    res = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user_id)
    )
    return res.scalar_one_or_none()


async def list_for_user(
    db: AsyncSession, user_id: int, *, page: int, page_size: int
) -> tuple[list[Report], int]:
    total = await db.scalar(
        select(func.count()).select_from(Report).where(Report.user_id == user_id)
    )
    res = await db.execute(
        select(Report)
        .where(Report.user_id == user_id)
        .order_by(Report.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(res.scalars().all()), int(total or 0)


async def delete(db: AsyncSession, report: Report) -> None:
    await db.delete(report)
    await db.flush()


async def count_for_user(db: AsyncSession, user_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(Report).where(Report.user_id == user_id)
        )
        or 0
    )


async def count_for_users(db: AsyncSession, user_ids: list[int]) -> dict[int, int]:
    """Report totals for many users in one query, keyed by user id.

    Avoids a per-row count when rendering the admin user directory.
    """
    if not user_ids:
        return {}
    res = await db.execute(
        select(Report.user_id, func.count())
        .where(Report.user_id.in_(user_ids))
        .group_by(Report.user_id)
    )
    return {user_id: int(total) for user_id, total in res.all()}
