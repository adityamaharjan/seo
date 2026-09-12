"""Site audit endpoints (submit / poll / list / delete).

A site audit is a separate product from a single-page analysis: it takes a
start URL and a page budget, crawls the site, and reports which problems repeat
across pages. It never takes target keywords — those belong to the single-page
feature, which judges one URL against terms its owner named.
"""
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbDep, enforce_quota, get_arq
from app.core.config import settings
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger
from app.crud import site_audit as audit_crud
from app.models.user import User
from app.schemas.site_audit import (
    PaginatedSiteAudits,
    SiteAuditAccepted,
    SiteAuditCreate,
    SiteAuditDetail,
    SiteAuditPageDetail,
    SiteAuditSummary,
)
from app.services import site_audit_service

logger = get_logger(__name__)

router = APIRouter(prefix="/site-audits", tags=["site-audits"])


@router.post("", response_model=SiteAuditAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_site_audit(
    payload: SiteAuditCreate,
    db: DbDep,
    arq: Annotated[ArqRedis, Depends(get_arq)],
    user: Annotated[User, Depends(enforce_quota)],
) -> SiteAuditAccepted:
    """Submit a site for a multi-page audit.

    One quota unit covers the whole crawl regardless of page count; the page
    budget is what bounds the work instead.
    """
    audit = await audit_crud.create_pending(
        db, user_id=user.id, url=str(payload.url), max_pages=payload.max_pages
    )

    # Commit before enqueueing. The worker can pick the job up within
    # milliseconds and would not see an uncommitted row.
    await db.commit()
    await db.refresh(audit)

    try:
        job = await arq.enqueue_job("run_site_audit_task", audit.id)
    except Exception as exc:
        logger.error("enqueue failed", extra={"audit_id": audit.id, "error": str(exc)})
        await site_audit_service.mark_failed(
            db, audit, "Could not queue the site audit job."
        )
        raise ServiceUnavailableError(
            "The analysis queue is unavailable. Your quota was not charged; "
            "please try again shortly."
        ) from exc

    audit.job_id = job.job_id if job else None
    await db.commit()
    await db.refresh(audit)
    return SiteAuditAccepted(
        id=audit.id,
        status=audit.status,
        status_url=f"{settings.API_V1_PREFIX}/site-audits/{audit.id}",
        max_pages=audit.max_pages,
    )


@router.get("", response_model=PaginatedSiteAudits)
async def list_site_audits(
    db: DbDep,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedSiteAudits:
    items, total = await audit_crud.list_for_user(
        db, user.id, page=page, page_size=page_size
    )
    return PaginatedSiteAudits(
        items=[SiteAuditSummary.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{audit_id}", response_model=SiteAuditDetail)
async def get_site_audit(audit_id: int, db: DbDep, user: CurrentUser) -> SiteAuditDetail:
    audit = await audit_crud.get_for_user(db, audit_id, user.id, with_pages=True)
    if audit is None:
        raise NotFoundError("Site audit not found.")
    return SiteAuditDetail.model_validate(audit)


@router.get("/{audit_id}/pages/{page_id}", response_model=SiteAuditPageDetail)
async def get_site_audit_page(
    audit_id: int, page_id: int, db: DbDep, user: CurrentUser
) -> SiteAuditPageDetail:
    """The full analysis for one crawled page, in the single-page report shape."""
    crawled = await audit_crud.get_page(db, audit_id, page_id, user.id)
    if crawled is None:
        raise NotFoundError("Page not found in this site audit.")
    return SiteAuditPageDetail.model_validate(crawled)


@router.delete("/{audit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site_audit(audit_id: int, db: DbDep, user: CurrentUser) -> None:
    audit = await audit_crud.get_for_user(db, audit_id, user.id)
    if audit is None:
        raise NotFoundError("Site audit not found.")
    await audit_crud.delete(db, audit)
    await db.commit()
