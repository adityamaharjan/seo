"""Performance checks derived from the HTTP fetch.

NOTE: These are server/transfer-level metrics measurable without a browser
(TTFB, total transfer time, payload size, compression, render-blocking
resource counts). Rendered Core Web Vitals (FCP, LCP, CLS, INP) require a real
browser or the Google PageSpeed Insights API and are intentionally out of
scope. :func:`check_core_web_vitals` exposes a disabled hook so a PageSpeed /
headless integration can be wired in later without restructuring.
"""
from app.seo.constants import (
    HTML_SIZE_GOOD_KB,
    HTML_SIZE_OK_KB,
    LOAD_GOOD_MS,
    LOAD_OK_MS,
    RENDER_BLOCKING_OK,
    TTFB_GOOD_MS,
    TTFB_OK_MS,
)
from app.seo.types import AnalysisContext, CheckResult

CATEGORY = "performance"

# Toggle when a real rendering backend (PageSpeed/headless) is integrated.
CORE_WEB_VITALS_ENABLED = False


def check_ttfb(ctx: AnalysisContext) -> CheckResult:
    ttfb = ctx.fetch.ttfb_ms
    if ttfb is None:
        return CheckResult(
            "ttfb", CATEGORY, "info", 100, "Time to first byte",
            "TTFB could not be measured.", value=None,
        )
    if ttfb <= TTFB_GOOD_MS:
        status, score, msg = "good", 100, "Excellent server response time."
    elif ttfb <= TTFB_OK_MS:
        status, score, msg = "good", 85, "Acceptable server response time."
    else:
        status, score, msg = "warning", 55, "Slow server response time."
    return CheckResult(
        "ttfb", CATEGORY, status, score, "Time to first byte",
        f"{msg} ({ttfb} ms).", value={"ttfb_ms": ttfb},
        recommendation=None if status == "good" else "Improve server response time or add a CDN.",
    )


def check_load_time(ctx: AnalysisContext) -> CheckResult:
    lt = ctx.fetch.load_time_ms
    if lt is None:
        return CheckResult(
            "load_time", CATEGORY, "info", 100, "Document download time",
            "Load time could not be measured.", value=None,
        )
    if lt <= LOAD_GOOD_MS:
        status, score, msg = "good", 100, "Fast document download."
    elif lt <= LOAD_OK_MS:
        status, score, msg = "good", 80, "Acceptable document download time."
    else:
        status, score, msg = "warning", 55, "Slow document download."
    return CheckResult(
        "load_time", CATEGORY, status, score, "Document download time",
        f"{msg} ({lt} ms).", value={"load_time_ms": lt},
        recommendation=None if status == "good" else "Reduce payload size and server latency.",
    )


def check_page_size(ctx: AnalysisContext) -> CheckResult:
    kb = round(ctx.fetch.html_size_bytes / 1024, 1)
    if kb <= HTML_SIZE_GOOD_KB:
        status, score, msg = "good", 100, "HTML payload is lean."
    elif kb <= HTML_SIZE_OK_KB:
        status, score, msg = "good", 80, "HTML payload is reasonable."
    else:
        status, score, msg = "warning", 55, "HTML payload is large."
    return CheckResult(
        "page_size", CATEGORY, status, score, "HTML size",
        f"{msg} ({kb} KB).",
        value={"html_size_kb": kb, "compressed": ctx.fetch.compressed},
        recommendation=None if status == "good" else "Minify HTML and remove unused markup.",
    )


def check_compression(ctx: AnalysisContext) -> CheckResult:
    if ctx.fetch.compressed:
        return CheckResult(
            "compression", CATEGORY, "good", 100, "Compression",
            "Response is compressed (gzip/br).",
            value=ctx.fetch.headers.get("content-encoding"),
        )
    return CheckResult(
        "compression", CATEGORY, "warning", 60, "Compression",
        "Response is not compressed.", value=None,
        recommendation="Enable gzip or brotli compression on the server.",
    )


def check_render_blocking(ctx: AnalysisContext) -> CheckResult:
    head = ctx.soup.find("head")
    scope = head if head else ctx.soup
    blocking_scripts = [
        s for s in scope.find_all("script", src=True)
        if not s.get("async") and not s.get("defer")
    ]
    blocking_css = scope.find_all("link", attrs={"rel": "stylesheet"})
    total = len(blocking_scripts) + len(blocking_css)
    status = "good" if total <= RENDER_BLOCKING_OK else "warning"
    return CheckResult(
        "render_blocking", CATEGORY, status,
        100 if status == "good" else max(40, 100 - (total - RENDER_BLOCKING_OK) * 8),
        "Render-blocking resources",
        f"{total} render-blocking resource(s) in <head>.",
        value={"scripts": len(blocking_scripts), "stylesheets": len(blocking_css)},
        recommendation=(
            "Defer/async non-critical JS and inline critical CSS."
            if status != "good" else None
        ),
    )


def check_core_web_vitals(ctx: AnalysisContext) -> CheckResult:
    """Placeholder for rendered metrics (FCP/LCP/CLS/INP).

    Disabled by default; returns an informational result so the contract is
    stable for the frontend until a PageSpeed/headless backend is wired in.
    """
    if not CORE_WEB_VITALS_ENABLED:
        return CheckResult(
            "core_web_vitals", CATEGORY, "info", 100, "Core Web Vitals",
            "Rendered Core Web Vitals require a browser and are not measured.",
            value={"enabled": False},
        )
    # Future: populate from ctx.extra["pagespeed"].
    return CheckResult(
        "core_web_vitals", CATEGORY, "info", 100, "Core Web Vitals",
        "Core Web Vitals data available.", value=ctx.extra.get("pagespeed"),
    )


CHECKS = [
    check_ttfb,
    check_load_time,
    check_page_size,
    check_compression,
    check_render_blocking,
    check_core_web_vitals,
]
