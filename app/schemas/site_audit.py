"""Site audit request/response schemas."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.core.config import settings
from app.models.site_audit import SiteAuditStatus
from app.seo import urlguard


class SiteAuditCreate(BaseModel):
    url: HttpUrl
    max_pages: int = Field(
        default=settings.SITE_AUDIT_DEFAULT_PAGES,
        ge=1,
        le=settings.SITE_AUDIT_MAX_PAGES,
        description="Upper bound on pages to crawl. The crawl may find fewer.",
    )

    @field_validator("url")
    @classmethod
    def _reject_non_public_targets(cls, v: HttpUrl) -> HttpUrl:
        """Reject obviously internal targets before any quota is consumed."""
        try:
            urlguard.validate_url(str(v))
        except urlguard.BlockedURLError as exc:
            raise ValueError(str(exc)) from exc
        return v


class SiteAuditSummary(BaseModel):
    """Lightweight row used in list views."""

    id: int
    start_url: str
    domain: str | None
    status: SiteAuditStatus
    max_pages: int
    pages_crawled: int
    pages_failed: int
    discovery_source: str | None
    overall_score: int | None
    overall_grade: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SiteAuditPageSummary(BaseModel):
    """One crawled page, without its full analysis payload."""

    id: int
    url: str
    final_url: str | None
    title: str | None
    status_code: int | None
    overall_score: int | None
    overall_grade: str | None
    ttfb_ms: float | None
    load_time_ms: float | None
    issue_counts: dict[str, int] | None
    error: str | None

    model_config = ConfigDict(from_attributes=True)


class SiteAuditPageDetail(SiteAuditPageSummary):
    """One crawled page including its full analysis, same shape as a report."""

    audit_id: int
    results: dict | None

    model_config = ConfigDict(from_attributes=True)


class SiteAuditDetail(SiteAuditSummary):
    """Full audit: the aggregate payload plus every crawled page."""

    job_id: str | None
    error: str | None
    # Site-level aggregate: category averages, ranked issues, score spread.
    results: dict[str, Any] | None
    pages: list[SiteAuditPageSummary] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedSiteAudits(BaseModel):
    items: list[SiteAuditSummary]
    total: int
    page: int
    page_size: int


class SiteAuditAccepted(BaseModel):
    """Returned by POST /site-audits (202)."""

    id: int
    status: SiteAuditStatus
    status_url: str
    max_pages: int
