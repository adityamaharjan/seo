"""SEO analysis endpoints (submit / poll / list / delete)."""
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbDep, enforce_quota, get_arq
from app.core.config import settings
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger
from app.crud import report as report_crud
from app.models.user import User
from app.schemas.report import (
    AnalysisAccepted,
    AnalysisCreate,
    PaginatedReports,
    ReportDetail,
    ReportSummary,
)
from app.services import report_service

logger = get_logger(__name__)

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(
    payload: AnalysisCreate,
    db: DbDep,
    arq: Annotated[ArqRedis, Depends(get_arq)],
    user: Annotated[User, Depends(enforce_quota)],
) -> AnalysisAccepted:
    """Submit a URL for analysis. Quota is consumed here; work runs in the
    background worker. Poll the returned ``status_url`` for the result."""
    report = await report_crud.create_pending(
        db,
        user_id=user.id,
        url=str(payload.url),
        target_keywords=payload.target_keywords,
    )

    # Commit before enqueueing. The worker can pick the job up within
    # milliseconds and would not see an uncommitted row.
    await db.commit()
    await db.refresh(report)

    try:
        job = await arq.enqueue_job("run_analysis_task", report.id)
    except Exception as exc:
        # The queue is down, so nothing will ever run this report. Fail it now
        # and give the quota unit back rather than leaving it pending forever.
        logger.error(
            "enqueue failed", extra={"report_id": report.id, "error": str(exc)}
        )
        await report_service.mark_failed(
            db, report, "Could not queue the analysis job."
        )
        raise ServiceUnavailableError(
            "The analysis queue is unavailable. Your quota was not charged; "
            "please try again shortly."
        ) from exc

    report.job_id = job.job_id if job else None
    await db.commit()
    await db.refresh(report)
    return AnalysisAccepted(
        id=report.id,
        status=report.status,
        status_url=f"{settings.API_V1_PREFIX}/analyses/{report.id}",
    )


@router.get("", response_model=PaginatedReports)
async def list_analyses(
    db: DbDep,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedReports:
    items, total = await report_crud.list_for_user(
        db, user.id, page=page, page_size=page_size
    )
    return PaginatedReports(
        items=[ReportSummary.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{report_id}", response_model=ReportDetail)
async def get_analysis(report_id: int, db: DbDep, user: CurrentUser) -> ReportDetail:
    report = await report_crud.get_for_user(db, report_id, user.id)
    if report is None:
        raise NotFoundError("Report not found.")
    return ReportDetail.model_validate(report)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(report_id: int, db: DbDep, user: CurrentUser) -> None:
    report = await report_crud.get_for_user(db, report_id, user.id)
    if report is None:
        raise NotFoundError("Report not found.")
    await report_crud.delete(db, report)
    await db.commit()
