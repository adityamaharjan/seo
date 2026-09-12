"""Data-access functions for site audits and their crawled pages."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.site_audit import SiteAudit, SiteAuditPage


async def create_pending(
    db: AsyncSession, *, user_id: int, url: str, max_pages: int
) -> SiteAudit:
    audit = SiteAudit(user_id=user_id, start_url=url, max_pages=max_pages)
    db.add(audit)
    await db.flush()
    return audit


async def get(db: AsyncSession, audit_id: int) -> SiteAudit | None:
    return await db.get(SiteAudit, audit_id)


async def get_for_user(
    db: AsyncSession, audit_id: int, user_id: int, *, with_pages: bool = False
) -> SiteAudit | None:
    stmt = select(SiteAudit).where(
        SiteAudit.id == audit_id, SiteAudit.user_id == user_id
    )
    if with_pages:
        # The detail view always renders the page table, so load it in one
        # round trip rather than lazily per row.
        stmt = stmt.options(selectinload(SiteAudit.pages))
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def get_page(
    db: AsyncSession, audit_id: int, page_id: int, user_id: int
) -> SiteAuditPage | None:
    """One crawled page, scoped through its audit so ownership is enforced."""
    res = await db.execute(
        select(SiteAuditPage)
        .join(SiteAudit, SiteAuditPage.audit_id == SiteAudit.id)
        .where(
            SiteAuditPage.id == page_id,
            SiteAuditPage.audit_id == audit_id,
            SiteAudit.user_id == user_id,
        )
    )
    return res.scalar_one_or_none()


async def list_for_user(
    db: AsyncSession, user_id: int, *, page: int, page_size: int
) -> tuple[list[SiteAudit], int]:
    total = await db.scalar(
        select(func.count()).select_from(SiteAudit).where(SiteAudit.user_id == user_id)
    )
    res = await db.execute(
        select(SiteAudit)
        .where(SiteAudit.user_id == user_id)
        .order_by(SiteAudit.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(res.scalars().all()), int(total or 0)


async def delete(db: AsyncSession, audit: SiteAudit) -> None:
    await db.delete(audit)
    await db.flush()
