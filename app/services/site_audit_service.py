"""Site audit orchestration: crawl a site, analyze each page, aggregate.

The crawl is bounded on every axis that could run away: pages, concurrency,
and wall-clock time. A site audit is one quota unit no matter how many pages it
covers, so the limits here are what stops it from being a free way to point the
server at an arbitrary number of URLs.
"""
import asyncio
import statistics
import time
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.crud import site_audit as audit_crud
from app.models.site_audit import (
    PSI_SAMPLE_SIZE,
    PsiScope,
    SiteAudit,
    SiteAuditPage,
    SiteAuditStatus,
)
from app.seo import analyzer, crawler, psi
from app.seo.scoring import STATUSES, grade
from app.services import api_key_service, quota_service

logger = get_logger(__name__)

# Issues affecting this share of crawled pages are site-wide patterns rather
# than one-off mistakes, and are surfaced as such.
_SITEWIDE_THRESHOLD = 0.5
# Example URLs carried with each ranked issue, so a fix has somewhere to start.
_EXAMPLES_PER_ISSUE = 5
# How long PageSpeed may run past the crawl deadline; must stay under the
# worker's 120s job-timeout margin.
_PSI_GRACE_SECONDS = 60


async def mark_failed(
    db: AsyncSession, audit: SiteAudit, error: str, *, refund: bool = True
) -> SiteAudit:
    """Mark an audit failed and hand back the quota unit it consumed."""
    audit.status = SiteAuditStatus.failed
    audit.error = error
    if refund and not audit.quota_refunded:
        await quota_service.refund(db, audit.user_id)
        audit.quota_refunded = True
    await db.commit()
    await db.refresh(audit)
    return audit


def _page_row(audit_id: int, url: str, result: dict) -> SiteAuditPage:
    timing = result.get("timing") or {}
    # internal_links exist only to drive the crawl; persisting a few hundred
    # URLs per page would dwarf the analysis itself.
    stored = {k: v for k, v in result.items() if k != "internal_links"}
    return SiteAuditPage(
        audit_id=audit_id,
        url=url,
        final_url=result.get("final_url"),
        title=(result.get("title") or "")[:512] or None,
        status_code=result.get("status_code"),
        overall_score=result.get("overall_score") if result.get("fetched_ok") else None,
        overall_grade=result.get("overall_grade") if result.get("fetched_ok") else None,
        ttfb_ms=timing.get("ttfb_ms"),
        load_time_ms=timing.get("load_time_ms"),
        issue_counts=result.get("issue_counts"),
        error=result.get("error"),
        results=stored,
    )


def _pagespeed_row(result: dict) -> dict:
    """One page's PageSpeed figures, read from its checks so they are the
    mobile numbers the page was scored on."""
    checks = {c["id"]: c for c in result.get("checks") or []}
    vitals = checks.get("core_web_vitals") or {}
    lab = vitals.get("value") or {}
    return {
        "url": result["final_url"],
        "title": result.get("title"),
        "performance": ((checks.get("lighthouse_performance") or {}).get("value") or {}).get("score"),
        "desktop_performance": (
            ((checks.get("lighthouse_performance") or {}).get("value") or {}).get("strategies") or {}
        ).get("desktop"),
        "vitals_status": vitals.get("status"),
        "lcp_ms": lab.get("lcp_ms"),
        "cls": lab.get("cls"),
        "tbt_ms": lab.get("tbt_ms"),
    }


def aggregate(start_url: str, results: list[tuple[str, dict]], *, source: str) -> dict:
    """Roll per-page analyses up into one site-level report.

    The useful site-level output is not an average — it is *which problems
    repeat*. A title-length warning on one page is a task; the same warning on
    forty pages is a template bug, and ranking issues by how many pages they
    touch is what tells those apart.
    """
    ok = [r for _, r in results if r.get("fetched_ok")]
    failed = [(u, r) for u, r in results if not r.get("fetched_ok")]
    scores = [r["overall_score"] for r in ok]

    issue_pages: dict[str, list[str]] = defaultdict(list)
    issue_meta: dict[str, dict] = {}
    category_totals: dict[str, list[int]] = defaultdict(list)
    category_weights: dict[str, float] = {}
    counts: Counter[str] = Counter()
    capped_pages: list[dict] = []

    for result in ok:
        for status, n in (result.get("issue_counts") or {}).items():
            counts[status] += n
        for category in result.get("category_scores") or []:
            category_totals[category["category"]].append(category["score"])
            category_weights[category["category"]] = category["weight"]
        if result.get("capped_by"):
            capped_pages.append(
                {
                    "url": result["final_url"],
                    "score": result["overall_score"],
                    "capped_by": result["capped_by"],
                }
            )
        for check in result.get("checks") or []:
            if check["status"] not in ("critical", "warning"):
                continue
            issue_pages[check["id"]].append(result["final_url"])
            # Keep the first occurrence's wording; every page says the same
            # thing and the recommendation is what the user acts on.
            issue_meta.setdefault(
                check["id"],
                {
                    "id": check["id"],
                    "label": check["label"],
                    "category": check["category"],
                    "status": check["status"],
                    "recommendation": check.get("recommendation"),
                },
            )
            # One critical page promotes the issue: the worst case is what
            # matters when the same check varies across a site.
            if check["status"] == "critical":
                issue_meta[check["id"]]["status"] = "critical"

    total_ok = len(ok)
    top_issues = sorted(
        (
            {
                **issue_meta[check_id],
                "affected_pages": len(pages),
                "total_pages": total_ok,
                "sitewide": total_ok > 0 and len(pages) / total_ok >= _SITEWIDE_THRESHOLD,
                "example_urls": pages[:_EXAMPLES_PER_ISSUE],
            }
            for check_id, pages in issue_pages.items()
        ),
        key=lambda i: (i["status"] != "critical", -i["affected_pages"], i["id"]),
    )

    categories = [
        {
            "category": name,
            "score": round(statistics.fmean(values)),
            "grade": grade(round(statistics.fmean(values))),
            "weight": category_weights.get(name, 0.0),
        }
        for name, values in sorted(
            category_totals.items(), key=lambda kv: -category_weights.get(kv[0], 0.0)
        )
    ]

    overall = round(statistics.fmean(scores)) if scores else 0
    worst = sorted(
        ({"url": r["final_url"], "title": r.get("title"), "score": r["overall_score"],
          "grade": r["overall_grade"]} for r in ok),
        key=lambda p: p["score"],
    )

    # Slowest first; a page whose Lighthouse score is missing sorts last.
    pagespeed = sorted(
        (_pagespeed_row(r) for r in ok if (r.get("psi") or {}).get("strategies")),
        key=lambda row: (row["performance"] is None, row["performance"] or 0),
    )

    return {
        "id": f"audit-{uuid.uuid4().hex[:8]}",
        "start_url": start_url,
        "domain": urlparse(start_url).netloc,
        "generated_at": datetime.now(UTC).isoformat(),
        "discovery_source": source,
        "pages_crawled": total_ok,
        "pages_failed": len(failed),
        "overall_score": overall,
        "overall_grade": grade(overall),
        "score_spread": {
            "min": min(scores) if scores else 0,
            "max": max(scores) if scores else 0,
            "median": round(statistics.median(scores)) if scores else 0,
        },
        "issue_counts": {status: counts.get(status, 0) for status in STATUSES},
        "category_scores": categories,
        "top_issues": top_issues,
        "worst_pages": worst[:10],
        "capped_pages": capped_pages,
        "pagespeed": pagespeed,
        "errors": [{"url": u, "error": r.get("error")} for u, r in failed],
    }


def _psi_budget(audit: SiteAudit) -> int:
    """How many pages of this crawl may get a PageSpeed run.

    Expressed as a count rather than a set of URLs because the page list is
    not known until the crawl is under way. Pages are analyzed in discovery
    order — breadth-first from the start URL — so spending the budget on the
    first N pages spends it on the shallowest, most linked-to ones.
    """
    scope = audit.psi_scope or PsiScope.off
    if scope == PsiScope.all:
        return audit.max_pages
    if scope == PsiScope.sample:
        return min(PSI_SAMPLE_SIZE, audit.max_pages)
    if scope == PsiScope.homepage:
        return 1
    return 0


async def _crawl(audit: SiteAudit, psi_key: str | None) -> tuple[list[tuple[str, dict]], str]:
    """Discover and analyze up to ``max_pages`` pages, newest frontier first."""
    start = crawler.normalize(audit.start_url)
    host = urlparse(start).netloc
    deadline = time.monotonic() + settings.SITE_AUDIT_TIMEOUT_SECONDS
    headers = {"User-Agent": settings.SEO_USER_AGENT}

    async with httpx.AsyncClient(
        timeout=15, follow_redirects=False, headers=headers, verify=True
    ) as client:
        signals = await crawler.load_site_signals(client, start)
        seeded = await crawler.urls_from_sitemaps(client, signals, limit=audit.max_pages)

    seen: set[str] = {start}
    queue: list[str] = [start]
    for url in seeded:
        if url not in seen:
            seen.add(url)
            queue.append(url)
    # With a sitemap the page list is already known, so link-following only
    # earns its keep when the sitemap came up short or absent.
    source = "sitemap" if seeded else "links"
    follow_links = len(queue) < audit.max_pages

    page_signals = signals.as_page_signals()
    results: list[tuple[str, dict]] = []
    semaphore = asyncio.Semaphore(settings.SITE_AUDIT_CONCURRENCY)
    # PageSpeed runs as its own tasks, beside the crawl rather than inside it:
    # a Lighthouse run is 10-30s against Google, and holding a crawl slot for
    # it would stall the whole batch and link discovery behind it. It gets its
    # own, higher limit because those calls cost the audited host nothing.
    psi_semaphore = asyncio.Semaphore(settings.PSI_CONCURRENCY)
    psi_stop = asyncio.Event()
    psi_budget = _psi_budget(audit) if psi_key else 0
    psi_tasks: dict[asyncio.Task, dict] = {}

    async def psi_one(result: dict, key: str) -> None:
        strategies, error = await psi.run_strategies(
            result["final_url"], key, semaphore=psi_semaphore, stop=psi_stop
        )
        try:
            analyzer.apply_psi(result, {"strategies": strategies, "error": error})
        except Exception as exc:  # the page keeps its PSI-less result
            logger.warning("psi merge failed", extra={"url": result["final_url"], "error": str(exc)})

    async def analyze_one(url: str) -> tuple[str, dict]:
        async with semaphore:
            try:
                return url, await analyzer.analyze(
                    url,
                    site_signals=page_signals,
                    collect_links=follow_links,
                    max_broken_checks=settings.SITE_AUDIT_BROKEN_LINK_CHECKS,
                )
            except Exception as exc:  # one bad page must not end the crawl
                logger.warning("page analysis failed", extra={"url": url, "error": str(exc)})
                return url, {"fetched_ok": False, "error": str(exc), "final_url": url}

    while queue and len(results) < audit.max_pages and time.monotonic() < deadline:
        # Never analyze more pages than the budget allows: an over-sized final
        # batch would fetch pages that are then thrown away.
        remaining = audit.max_pages - len(results)
        batch = queue[: min(settings.SITE_AUDIT_CONCURRENCY, remaining)]
        del queue[: len(batch)]
        for url, result in await asyncio.gather(*(analyze_one(u) for u in batch)):
            results.append((url, result))
            # Pages arrive in discovery order, so a scope narrower than the
            # crawl spends its budget on the shallowest, most linked-to pages.
            # Only fetched pages count against it.
            if psi_key and result.get("fetched_ok") and len(psi_tasks) < psi_budget:
                psi_tasks[asyncio.create_task(psi_one(result, psi_key))] = result
            # Stop discovering once enough URLs are known. Filtering marks a URL
            # as seen, so looking for links we have no room to queue would
            # retire them permanently and leave the crawl short of its budget.
            if not follow_links or len(results) + len(queue) >= audit.max_pages:
                continue
            discovered = crawler.links_worth_following(
                result.get("internal_links") or [], signals, host, seen
            )
            if discovered:
                source = "mixed" if seeded else "links"
            queue.extend(discovered)

    if psi_tasks:
        # The grace keeps PSI inside the worker's job timeout, which allows the
        # crawl deadline plus 120s.
        _, pending = await asyncio.wait(
            psi_tasks, timeout=max(deadline - time.monotonic(), 0) + _PSI_GRACE_SECONDS
        )
        for task in pending:
            task.cancel()
            analyzer.apply_psi(psi_tasks[task], {"strategies": {}, "error": (
                "Skipped: the audit ran out of time before PageSpeed reached this page."
            )})

    return results, source


async def run_site_audit(db: AsyncSession, audit_id: int) -> SiteAudit:
    """Execute a queued site audit and persist every page plus the aggregate."""
    audit = await audit_crud.get(db, audit_id)
    if audit is None:
        raise ValueError(f"Site audit {audit_id} not found")

    audit.status = SiteAuditStatus.running
    await db.commit()

    # Resolved here rather than carried through the queue, so a decrypted key
    # never lands in a Redis job payload.
    psi_key = None
    if audit.used_psi:
        psi_key = await api_key_service.resolve_psi_key(
            db, audit.user_id, requested=None
        )
        if psi_key is None:
            logger.warning("psi requested but no key available",
                           extra={"audit_id": audit_id})
            audit.used_psi = False

    try:
        results, source = await _crawl(audit, psi_key)
    except Exception as exc:
        logger.exception("site audit crashed", extra={"audit_id": audit_id})
        return await mark_failed(db, audit, str(exc))

    if psi_key:
        # One outcome for the whole crawl: an error on any page is worth
        # surfacing (it is almost always quota exhaustion, which will affect
        # every later run too), while a single success proves the key works.
        psi_errors = [
            (r.get("psi") or {}).get("error") for _, r in results
        ]
        any_success = any((r.get("psi") or {}).get("strategies") for _, r in results)
        await api_key_service.record_psi_outcome(
            db,
            audit.user_id,
            error=None if any_success else next((e for e in psi_errors if e), None),
        )
        audit.used_psi = any_success

    if not results or not any(r.get("fetched_ok") for _, r in results):
        first_error = next(
            (r.get("error") for _, r in results if r.get("error")), None
        )
        return await mark_failed(
            db, audit, first_error or "No pages could be crawled at this URL."
        )

    summary = aggregate(audit.start_url, results, source=source)
    for url, result in results:
        db.add(_page_row(audit.id, url, result))

    audit.domain = summary["domain"]
    audit.discovery_source = source
    audit.pages_crawled = summary["pages_crawled"]
    audit.pages_failed = summary["pages_failed"]
    audit.overall_score = summary["overall_score"]
    audit.overall_grade = summary["overall_grade"]
    audit.results = summary
    audit.status = SiteAuditStatus.done
    await db.commit()
    await db.refresh(audit)
    return audit
