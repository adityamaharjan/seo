"""Schemas describing the structured SEO analysis result.

These mirror the dataclasses produced by the SEO engine and define the public
JSON contract consumed by the frontend.
"""
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class CheckStatus(StrEnum):
    good = "good"
    warning = "warning"
    critical = "critical"
    info = "info"


class Category(StrEnum):
    meta = "meta"
    content = "content"
    structure = "structure"
    links = "links"
    indexability = "indexability"
    performance = "performance"
    security = "security"
    mobile = "mobile"


class CheckResult(BaseModel):
    id: str
    category: Category
    status: CheckStatus
    score: int  # 0-100
    label: str
    value: Any = None
    message: str
    recommendation: str | None = None


class IssueCounts(BaseModel):
    """How many checks landed in each status, for an at-a-glance summary."""

    critical: int = 0
    warning: int = 0
    good: int = 0
    info: int = 0


class CategoryScore(BaseModel):
    category: Category
    score: int
    grade: str
    weight: float
    checks: list[str]  # check ids belonging to this category


class Timing(BaseModel):
    ttfb_ms: float | None = None
    load_time_ms: float | None = None
    transfer_size_kb: float | None = None
    html_size_kb: float | None = None
    compressed: bool | None = None
    redirect_count: int = 0


class SEOResult(BaseModel):
    id: str
    url: str
    final_url: str
    domain: str
    generated_at: str
    fetched_ok: bool
    status_code: int | None = None
    overall_score: int
    overall_grade: str
    # The weighted score before indexability caps; equal to overall_score
    # unless capped_by is non-empty.
    uncapped_score: int
    capped_by: list[str] = []
    issue_counts: IssueCounts
    timing: Timing
    category_scores: list[CategoryScore]
    checks: list[CheckResult]
    error: str | None = None
