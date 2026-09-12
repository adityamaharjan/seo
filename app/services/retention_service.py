"""Scheduled data retention.

Report payloads, site-audit payloads and refresh-token rows all grow without
bound: the ``results`` JSON is large, a site audit carries one of those per
crawled page, and every rotation leaves a dead token behind. The worker runs
:func:`purge` nightly so the tables stay a working set rather than an archive.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.refresh_token import RefreshToken
from app.models.report import Report
from app.models.site_audit import SiteAudit

logger = get_logger(__name__)


async def purge(db: AsyncSession) -> dict[str, int]:
    """Delete aged reports and dead refresh tokens. Returns rows removed."""
    now = datetime.now(UTC)
    removed: dict[str, int] = {}

    if settings.REPORT_RETENTION_DAYS > 0:
        cutoff = now - timedelta(days=settings.REPORT_RETENTION_DAYS)
        result = await db.execute(delete(Report).where(Report.created_at < cutoff))
        removed["reports"] = result.rowcount or 0

        # Site audits store a full analysis per crawled page, so one audit can
        # be fifty times the payload of a single report. Leaving them out of
        # the sweep would let them dominate the database. Their pages go with
        # them through the FK cascade.
        result = await db.execute(
            delete(SiteAudit).where(SiteAudit.created_at < cutoff)
        )
        removed["site_audits"] = result.rowcount or 0

    token_cutoff = now - timedelta(days=settings.TOKEN_RETENTION_DAYS)
    result = await db.execute(
        delete(RefreshToken).where(
            or_(
                RefreshToken.expires_at < token_cutoff,
                RefreshToken.revoked.is_(True),
            )
        )
    )
    removed["refresh_tokens"] = result.rowcount or 0

    await db.commit()
    logger.info("retention purge complete", extra=removed)
    return removed
