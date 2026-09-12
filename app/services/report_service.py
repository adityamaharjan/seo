"""Report orchestration: create a pending report and run/persist analysis.

The same ``run_analysis`` routine is used by the ARQ worker and by tests; it is
deliberately decoupled from any web-request context.
"""
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.crud import report as report_crud
from app.models.report import Report, ReportStatus
from app.seo import analyzer
from app.services import quota_service

logger = get_logger(__name__)


async def mark_failed(
    db: AsyncSession, report: Report, error: str, *, refund: bool = True
) -> Report:
    """Mark a report failed and hand back the quota unit it consumed.

    A failure means the user got no analysis, so charging them for it is wrong.
    ``quota_refunded`` makes this idempotent: a retried job cannot refund the
    same report twice.
    """
    report.status = ReportStatus.failed
    report.error = error
    if refund and not report.quota_refunded:
        await quota_service.refund(db, report.user_id)
        report.quota_refunded = True
    await db.commit()
    await db.refresh(report)
    return report


async def run_analysis(db: AsyncSession, report_id: int) -> Report:
    """Execute the SEO analysis for a report and persist the outcome."""
    report = await report_crud.get(db, report_id)
    if report is None:
        raise ValueError(f"Report {report_id} not found")

    report.status = ReportStatus.running
    await db.commit()

    try:
        result = await analyzer.analyze(
            report.url, target_keywords=report.target_keywords or []
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("analysis crashed", extra={"report_id": report_id})
        return await mark_failed(db, report, str(exc))

    report.results = result
    report.final_url = result.get("final_url")
    report.domain = result.get("domain") or urlparse(report.url).netloc
    report.title = (result.get("title") or "")[:512] or None
    report.overall_score = result.get("overall_score")
    report.overall_grade = result.get("overall_grade")
    timing = result.get("timing") or {}
    report.ttfb_ms = timing.get("ttfb_ms")
    report.load_time_ms = timing.get("load_time_ms")

    if result.get("fetched_ok"):
        report.status = ReportStatus.done
        await db.commit()
        await db.refresh(report)
        return report

    return await mark_failed(
        db, report, result.get("error") or "Analysis failed."
    )
