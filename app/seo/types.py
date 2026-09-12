"""Internal dataclasses used by the SEO engine.

These are converted to the Pydantic schemas in :mod:`app.schemas.seo` at the
API boundary; keeping them as plain dataclasses keeps the check functions
fast and dependency-light.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup


@dataclass
class FetchResult:
    """Everything the fetcher learns about a single HTTP retrieval."""

    requested_url: str
    final_url: str
    domain: str
    status_code: int
    ok: bool
    content: bytes
    text: str
    headers: dict[str, str]
    ttfb_ms: float | None
    load_time_ms: float | None
    transfer_size_bytes: int
    html_size_bytes: int
    compressed: bool
    redirect_count: int
    error: str | None = None


@dataclass
class AnalysisContext:
    """Shared, pre-computed data passed to every check function."""

    fetch: FetchResult
    soup: BeautifulSoup
    clean_text: str
    tokens: list[str]
    word_count: int
    # Keywords the submitter wants this page to rank for. Empty is the norm;
    # keyword placement is then reported as informational and left unscored.
    target_keywords: list[str] = field(default_factory=list)
    # Populated lazily by async checks that perform extra network calls.
    robots_txt: str | None = None
    sitemap_found: bool | None = None
    broken_links: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    id: str
    category: str
    status: str  # good | warning | critical | info
    score: int  # 0-100
    label: str
    message: str
    value: Any = None
    recommendation: str | None = None
