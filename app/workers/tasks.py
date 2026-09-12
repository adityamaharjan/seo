"""Background tasks executed by the ARQ worker."""
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.services import report_service, retention_service, site_audit_service

logger = get_logger(__name__)


async def run_analysis_task(ctx: dict, report_id: int) -> dict:
    """Run a queued SEO analysis and persist the result."""
    logger.info("running analysis", extra={"report_id": report_id})
    async with AsyncSessionLocal() as db:
        report = await report_service.run_analysis(db, report_id)
        return {"report_id": report.id, "status": report.status.value}


async def run_site_audit_task(ctx: dict, audit_id: int) -> dict:
    """Crawl a site and persist the aggregate plus every analyzed page."""
    logger.info("running site audit", extra={"audit_id": audit_id})
    async with AsyncSessionLocal() as db:
        audit = await site_audit_service.run_site_audit(db, audit_id)
        return {
            "audit_id": audit.id,
            "status": audit.status.value,
            "pages_crawled": audit.pages_crawled,
        }


async def purge_old_data_task(ctx: dict) -> dict:
    """Nightly retention sweep (registered as a cron job)."""
    async with AsyncSessionLocal() as db:
        return await retention_service.purge(db)
