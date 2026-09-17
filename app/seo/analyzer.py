"""SEO analysis orchestrator.

Flow: fetch the page -> parse once -> gather async signals (robots.txt,
sitemap, broken links) -> run all synchronous checks -> score -> assemble the
:class:`SEOResult` contract.
"""
import asyncio
import uuid
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.logging import get_logger
from app.seo import fetcher, psi, urlguard
from app.seo.checks import ALL_CHECKS
from app.seo.checks.links import classify_links
from app.seo.keywords import analyze_keywords
from app.seo.scoring import STATUSES, grade, score_categories
from app.seo.text import extract_clean_text, tokenize
from app.seo.types import AnalysisContext, CheckResult, FetchResult

logger = get_logger(__name__)


def _error_result(fetch: FetchResult) -> dict:
    return {
        "id": f"report-{uuid.uuid4().hex[:8]}",
        "url": fetch.requested_url,
        "final_url": fetch.final_url,
        "domain": fetch.domain,
        "generated_at": datetime.now(UTC).isoformat(),
        "fetched_ok": False,
        "status_code": fetch.status_code or None,
        "overall_score": 0,
        "overall_grade": "F",
        "uncapped_score": 0,
        "capped_by": [],
        "keyword_report": None,
        "issue_counts": dict.fromkeys(STATUSES, 0),
        "timing": {
            "ttfb_ms": fetch.ttfb_ms,
            "load_time_ms": fetch.load_time_ms,
            "transfer_size_kb": round(fetch.transfer_size_bytes / 1024, 1),
            "html_size_kb": round(fetch.html_size_bytes / 1024, 1),
            "compressed": fetch.compressed,
            "redirect_count": fetch.redirect_count,
        },
        "category_scores": [],
        "checks": [],
        "error": fetch.error or f"Fetch failed with status {fetch.status_code}",
    }


async def _gather_async_signals(
    ctx: AnalysisContext,
    site_signals: dict | None = None,
    *,
    max_broken_checks: int | None = None,
) -> None:
    """Fetch robots.txt, sitemap, favicon, and sample broken links concurrently.

    ``site_signals`` lets a site audit hand over robots.txt and sitemap presence
    it already fetched. Those two are properties of the host, not the page, so
    re-fetching them for every URL in a 50-page crawl is pure waste.

    ``max_broken_checks`` overrides how many links are probed. A crawl runs
    several pages at once, so the per-page default would multiply into a
    punishing number of concurrent requests against one host.
    """
    sample_size = (
        settings.SEO_MAX_BROKEN_LINK_CHECKS
        if max_broken_checks is None
        else max_broken_checks
    )
    base = f"{urlparse(ctx.fetch.final_url).scheme}://{ctx.fetch.domain}"
    headers = {"User-Agent": settings.SEO_USER_AGENT}

    async with httpx.AsyncClient(
        timeout=10, follow_redirects=False, headers=headers, verify=True
    ) as client:

        async def _guarded_get(path: str) -> httpx.Response | None:
            """GET a site-root file, re-checking the SSRF guard on each hop."""
            target = urljoin(base + "/", path)
            for _ in range(settings.SEO_MAX_REDIRECTS):
                await urlguard.check_url(target)
                resp = await client.get(target)
                urlguard.assert_peer_public(resp)
                if resp.has_redirect_location and resp.next_request is not None:
                    target = str(resp.next_request.url)
                    continue
                return resp
            return None

        async def get_robots() -> None:
            try:
                r = await _guarded_get("robots.txt")
                ctx.robots_txt = r.text if r is not None and r.status_code < 400 else None
            except (httpx.HTTPError, urlguard.BlockedURLError):
                ctx.robots_txt = None

        async def get_sitemap() -> None:
            try:
                r = await _guarded_get("sitemap.xml")
                ctx.sitemap_found = bool(
                    r is not None
                    and r.status_code < 400
                    and "xml" in r.headers.get("content-type", "")
                )
            except (httpx.HTTPError, urlguard.BlockedURLError):
                ctx.sitemap_found = False

        async def get_favicon() -> None:
            """Resolve the page's favicon, declared or (the common case) not.

            Most sites never add a <link rel="icon"> and rely entirely on the
            browser's default /favicon.ico fallback, so a declared link is
            only one of two ways a favicon can be present. A declared link is
            also just a string in the HTML until it's actually fetched, so we
            verify it resolves rather than taking its presence on faith.
            """
            icon = ctx.soup.find("link", attrs={"rel": lambda v: v and "icon" in v.lower()})
            href = (icon.get("href") or "").strip() if icon else ""
            ctx.extra["favicon_declared"] = bool(href)
            for candidate in filter(None, [href, "favicon.ico"]):
                try:
                    r = await _guarded_get(candidate)
                except (httpx.HTTPError, urlguard.BlockedURLError):
                    continue
                if r is not None and r.status_code < 400 and r.content:
                    ctx.extra["favicon_url"] = str(r.url)
                    return
            ctx.extra["favicon_url"] = None

        async def check_broken() -> None:
            links = ctx.extra.get("internal_links", []) + ctx.extra.get(
                "external_links", []
            )
            sample = links[:sample_size]
            results = await asyncio.gather(
                *(fetcher.head_ok(client, u) for u in sample), return_exceptions=True
            )
            ctx.broken_links = [
                u for u, ok in zip(sample, results, strict=False) if ok is not True
            ]

        if site_signals is None:
            await asyncio.gather(get_robots(), get_sitemap(), get_favicon())
        else:
            ctx.robots_txt = site_signals.get("robots_txt")
            ctx.sitemap_found = bool(site_signals.get("sitemap_found"))
            await get_favicon()

        # Broken-link sampling needs the page's links, so classify them first.
        # It also has to happen *inside* this block: the sampling used to be
        # handed back to the caller and run after the `async with` had closed
        # the client, so every probe raised "client has been closed" and every
        # sampled link was reported broken on every report.
        classify_links(ctx)
        await check_broken()


async def _run_psi(
    ctx: AnalysisContext,
    api_key: str,
    strategies: list[str] | None,
    semaphore: asyncio.Semaphore | None,
) -> None:
    """Attach PageSpeed Insights data to ``ctx.extra['psi']``.

    Runs against the *final* URL so a redirect does not send Lighthouse to a
    page that immediately bounces. Never raises: PSI is enrichment, and a
    Google outage must not cost the user their whole report.
    """
    results, error = await psi.run_strategies(
        ctx.fetch.final_url, api_key, strategies, semaphore=semaphore
    )
    ctx.extra["psi"] = {"strategies": results, "error": error}


async def analyze(
    url: str,
    target_keywords: list[str] | None = None,
    *,
    site_signals: dict | None = None,
    collect_links: bool = False,
    max_broken_checks: int | None = None,
    psi_key: str | None = None,
    psi_strategies: list[str] | None = None,
    psi_semaphore: asyncio.Semaphore | None = None,
) -> dict:
    """Run a full analysis and return a JSON-serializable result dict.

    ``collect_links`` adds the page's internal links under ``internal_links``.
    A site audit needs them to walk a site that has no sitemap; the single-page
    path leaves them out because they are large and nothing reads them.

    ``psi_key`` turns on the PageSpeed Insights checks. Without one the
    PSI-backed checks report themselves as unavailable and go unscored, so the
    result keeps the same shape either way.
    """
    fetch = await fetcher.fetch(url)
    if not fetch.ok or not fetch.text:
        return _error_result(fetch)

    soup = BeautifulSoup(fetch.content, "lxml")
    clean_text = extract_clean_text(soup)
    tokens = tokenize(clean_text)

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    ctx = AnalysisContext(
        fetch=fetch,
        soup=soup,
        clean_text=clean_text,
        tokens=tokens,
        word_count=len(tokens),
        target_keywords=list(target_keywords or []),
    )

    # 1) Site-level signals, link classification and broken-link sampling, all
    #    within one HTTP client's lifetime. A PSI run is 10-30s against Google
    #    while these are short requests to the target host, so overlapping them
    #    makes PSI close to free in wall-clock terms instead of doubling the
    #    time an analysis takes.
    signal_work = [
        _gather_async_signals(ctx, site_signals, max_broken_checks=max_broken_checks)
    ]
    if psi_key:
        signal_work.append(_run_psi(ctx, psi_key, psi_strategies, psi_semaphore))
    await asyncio.gather(*signal_work)

    # 2) Run every synchronous check.
    checks: list[CheckResult] = []
    for check in ALL_CHECKS:
        try:
            checks.append(check(ctx))
        except Exception as exc:  # never let one check abort the report
            logger.warning(
                "check failed",
                extra={"check": getattr(check, "__name__", "?"), "error": str(exc)},
            )

    breakdown = score_categories(checks)

    result = {
        "id": f"report-{uuid.uuid4().hex[:8]}",
        "url": fetch.requested_url,
        "final_url": fetch.final_url,
        "domain": fetch.domain,
        "generated_at": datetime.now(UTC).isoformat(),
        "fetched_ok": True,
        "status_code": fetch.status_code,
        "overall_score": breakdown.overall,
        "overall_grade": breakdown.grade,
        "uncapped_score": breakdown.uncapped_overall,
        "capped_by": breakdown.capped_by,
        # Keyword targeting rides along in the same response but is scored
        # independently and never folded into overall_score.
        "keyword_report": analyze_keywords(ctx),
        "issue_counts": breakdown.issue_counts,
        "title": title,
        "timing": {
            "ttfb_ms": fetch.ttfb_ms,
            "load_time_ms": fetch.load_time_ms,
            "transfer_size_kb": round(fetch.transfer_size_bytes / 1024, 1),
            "html_size_kb": round(fetch.html_size_bytes / 1024, 1),
            "compressed": fetch.compressed,
            "redirect_count": fetch.redirect_count,
        },
        "category_scores": breakdown.categories,
        "checks": [c.__dict__ for c in checks],
        # Carried whole so the report can show both strategies side by side,
        # while the checks above score the mobile one.
        "psi": ctx.extra.get("psi"),
        "error": None,
    }
    if collect_links:
        result["internal_links"] = ctx.extra.get("internal_links", [])
    return result


__all__ = ["analyze", "grade"]
