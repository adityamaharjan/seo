"""Report request/response schemas."""
import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.report import ReportStatus
from app.seo import urlguard
from app.seo.constants import MAX_TARGET_KEYWORDS


class AnalysisCreate(BaseModel):
    url: HttpUrl
    # Terms this page should be judged against. Optional: with none given,
    # keyword placement is reported as informational and left unscored.
    target_keywords: list[str] = Field(default_factory=list)
    # Whether to enrich this run with PageSpeed Insights. None means "use
    # whatever my account has": the request stays valid for a caller that has
    # never heard of PageSpeed, while True is an explicit ask that fails
    # loudly when no key is stored.
    use_psi: bool | None = Field(
        default=None,
        description=(
            "True to require PageSpeed Insights data, False to skip it, "
            "omitted to use the account's saved key when there is one."
        ),
    )

    @field_validator("target_keywords")
    @classmethod
    def _clean_keywords(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in v:
            keyword = re.sub(r"\s+", " ", raw).strip()
            if not keyword:
                continue
            if len(keyword) > 100:
                raise ValueError("Each keyword must be 100 characters or fewer.")
            if keyword.lower() not in {k.lower() for k in cleaned}:
                cleaned.append(keyword)
        if len(cleaned) > MAX_TARGET_KEYWORDS:
            raise ValueError(
                f"At most {MAX_TARGET_KEYWORDS} target keywords can be checked at once."
            )
        return cleaned

    @field_validator("url")
    @classmethod
    def _reject_non_public_targets(cls, v: HttpUrl) -> HttpUrl:
        """Reject obviously internal targets before any quota is consumed.

        Only the checks that need no DNS run here so the request stays fast;
        name resolution and the connected-peer check happen in the fetcher.
        """
        try:
            urlguard.validate_url(str(v))
        except urlguard.BlockedURLError as exc:
            raise ValueError(str(exc)) from exc
        return v


class ReportSummary(BaseModel):
    """Lightweight row used in list views."""

    id: int
    url: str
    domain: str | None
    status: ReportStatus
    title: str | None
    target_keywords: list[str] | None
    overall_score: int | None
    overall_grade: str | None
    used_psi: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportDetail(ReportSummary):
    """Full report including the structured results payload."""

    final_url: str | None
    job_id: str | None
    error: str | None
    ttfb_ms: float | None
    load_time_ms: float | None
    results: dict | None

    model_config = ConfigDict(from_attributes=True)


class PaginatedReports(BaseModel):
    items: list[ReportSummary]
    total: int
    page: int
    page_size: int


class AnalysisAccepted(BaseModel):
    """Returned by POST /analyses (202)."""

    id: int
    status: ReportStatus
    status_url: str
