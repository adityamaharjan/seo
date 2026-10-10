"""Performance checks.

Two tiers live here. The first is server/transfer-level metrics measurable
from the HTTP fetch alone (TTFB, transfer time, payload size, compression,
render-blocking resource counts) — these always run.

The second is rendered metrics, which need a real browser. They come from the
Google PageSpeed Insights API and therefore only appear when the user ran the
analysis with a PSI key. Every PSI-backed check degrades to an informational
result when ``ctx.extra["psi"]`` is absent, so a report without a key keeps the
exact shape a report with one has, and info results are not scored.
"""
from app.seo.constants import (
    CLS_GOOD,
    CLS_OK,
    HTML_SIZE_GOOD_KB,
    HTML_SIZE_OK_KB,
    INP_GOOD_MS,
    INP_OK_MS,
    LCP_GOOD_MS,
    LCP_OK_MS,
    LIGHTHOUSE_GOOD,
    LIGHTHOUSE_OK,
    LOAD_GOOD_MS,
    LOAD_OK_MS,
    RENDER_BLOCKING_OK,
    TBT_GOOD_MS,
    TBT_OK_MS,
    TTFB_GOOD_MS,
    TTFB_OK_MS,
)
from app.seo.types import AnalysisContext, CheckResult

CATEGORY = "performance"


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


def _psi(ctx: AnalysisContext) -> dict | None:
    """The primary strategy's PSI data, or None when PSI did not run.

    Mobile is preferred whenever both strategies ran: Google indexes and ranks
    on the mobile crawl, so scoring the desktop numbers would grade the page on
    something search does not use. Desktop still travels in the payload for the
    report to display alongside.
    """
    psi = ctx.extra.get("psi") or {}
    runs = psi.get("strategies") or {}
    return runs.get("mobile") or next(iter(runs.values()), None)


def _unavailable(check_id: str, label: str, ctx: AnalysisContext) -> CheckResult:
    """Uniform 'PSI did not run' result: informational, and never scored."""
    reason = (ctx.extra.get("psi") or {}).get("error")
    return CheckResult(
        check_id, CATEGORY, "info", 100, label,
        reason or "Add a PageSpeed Insights API key to measure this.",
        value={"available": False},
        recommendation=None,
    )


def _band(value: float, good: float, ok: float) -> tuple[str, int]:
    """Map a metric onto Google's good / needs-improvement / poor banding."""
    if value <= good:
        return "good", 100
    if value <= ok:
        return "warning", 65
    return "critical", 30


def check_core_web_vitals(ctx: AnalysisContext) -> CheckResult:
    """Lab Core Web Vitals from a Lighthouse run (LCP, CLS, TBT).

    Lab data is a single reproducible measurement from Google's own hardware.
    It is the diagnostic view: it says what the page does, whereas the field
    check below says what real visitors experienced.
    """
    data = _psi(ctx)
    if not data or not data.get("lab"):
        return _unavailable("core_web_vitals", "Core Web Vitals (lab)", ctx)

    lab = data["lab"]
    parts: list[tuple[str, str, int]] = []
    if (lcp := lab.get("lcp_ms")) is not None:
        status, score = _band(lcp, LCP_GOOD_MS, LCP_OK_MS)
        parts.append((f"LCP {lcp / 1000:.1f}s", status, score))
    if (cls := lab.get("cls")) is not None:
        status, score = _band(cls, CLS_GOOD, CLS_OK)
        parts.append((f"CLS {cls:.3f}", status, score))
    if (tbt := lab.get("tbt_ms")) is not None:
        status, score = _band(tbt, TBT_GOOD_MS, TBT_OK_MS)
        parts.append((f"TBT {round(tbt)}ms", status, score))

    if not parts:
        return _unavailable("core_web_vitals", "Core Web Vitals (lab)", ctx)

    # The worst metric decides: passing Core Web Vitals requires all of them to
    # pass, so averaging would let a good CLS disguise a failing LCP.
    worst = min(p[2] for p in parts)
    status = next(p[1] for p in parts if p[2] == worst)
    failing = [p[0] for p in parts if p[2] < 100]
    return CheckResult(
        "core_web_vitals", CATEGORY, status, worst, "Core Web Vitals (lab)",
        ", ".join(p[0] for p in parts) + (
            "." if not failing else f". Outside Google's thresholds: {', '.join(failing)}."
        ),
        value=lab,
        recommendation=(
            None if status == "good"
            else "Improve the failing metric: LCP is dominated by the largest image "
                 "or text block, CLS by elements without reserved space, and TBT by "
                 "long JavaScript tasks."
        ),
    )


def check_field_vitals(ctx: AnalysisContext) -> CheckResult:
    """Core Web Vitals as experienced by real Chrome users (CrUX).

    This is the measurement Google ranks on, so it outweighs the lab figures.
    Most URLs have no field data at all — CrUX only reports pages with enough
    traffic to be statistically sound — so the origin-wide numbers stand in
    when the specific URL is too quiet, and the result says which was used.
    """
    data = _psi(ctx)
    if not data:
        return _unavailable("field_vitals", "Core Web Vitals (field data)", ctx)

    field, scope = data.get("field"), "this URL"
    if not field:
        field, scope = data.get("origin_field"), "this origin"
    if not field:
        return CheckResult(
            "field_vitals", CATEGORY, "info", 100, "Core Web Vitals (field data)",
            "Chrome has too little real-user traffic for this page to report field "
            "data. This is normal for a low-traffic site and is not a fault.",
            value={"available": False},
        )

    parts: list[tuple[str, str, int]] = []
    for key, label, good, ok, fmt in (
        ("lcp_ms", "LCP", LCP_GOOD_MS, LCP_OK_MS, lambda v: f"{v / 1000:.1f}s"),
        ("inp_ms", "INP", INP_GOOD_MS, INP_OK_MS, lambda v: f"{round(v)}ms"),
        ("cls", "CLS", CLS_GOOD, CLS_OK, lambda v: f"{v:.3f}"),
    ):
        value = field.get(key)
        if value is None:
            continue
        status, score = _band(value, good, ok)
        parts.append((f"{label} {fmt(value)}", status, score))

    if not parts:
        return _unavailable("field_vitals", "Core Web Vitals (field data)", ctx)

    worst = min(p[2] for p in parts)
    status = next(p[1] for p in parts if p[2] == worst)
    failing = [p[0] for p in parts if p[2] < 100]
    return CheckResult(
        "field_vitals", CATEGORY, status, worst, "Core Web Vitals (field data)",
        f"Real-user data for {scope} (75th percentile): "
        + ", ".join(p[0] for p in parts)
        + ("." if not failing else f". Failing: {', '.join(failing)}."),
        value={**field, "scope": scope},
        recommendation=(
            None if status == "good"
            else "These are the numbers Google uses for the Core Web Vitals ranking "
                 "signal, so fixing them affects rankings directly."
        ),
    )


def check_lighthouse_performance(ctx: AnalysisContext) -> CheckResult:
    """Lighthouse's own weighted performance score, 0-100."""
    data = _psi(ctx)
    score = (data or {}).get("scores", {}).get("performance")
    if score is None:
        return _unavailable("lighthouse_performance", "Lighthouse performance", ctx)

    if score >= LIGHTHOUSE_GOOD:
        status = "good"
    elif score >= LIGHTHOUSE_OK:
        status = "warning"
    else:
        status = "critical"
    by_strategy = {
        name: run.get("scores", {}).get("performance")
        for name, run in ((ctx.extra.get("psi") or {}).get("strategies") or {}).items()
    }
    # Only mobile is scored; any other strategy that ran is named here, since
    # this message is the only place the report shows it.
    others = ", ".join(
        f"{name} {value}/100" for name, value in by_strategy.items()
        if name != "mobile" and value is not None and "mobile" in by_strategy
    )
    return CheckResult(
        "lighthouse_performance", CATEGORY, status, score, "Lighthouse performance",
        f"Lighthouse scores this page {score}/100 for performance"
        + (f" on mobile ({others})." if others else "."),
        value={"score": score, "strategies": by_strategy},
        recommendation=(
            None if status == "good"
            else "See the PageSpeed opportunities below for the specific changes "
                 "Lighthouse estimates will move this score most."
        ),
    )


def check_pagespeed_opportunities(ctx: AnalysisContext) -> CheckResult:
    """Lighthouse's ranked list of concrete fixes.

    Informational on purpose. Every opportunity here is already reflected in
    the Lighthouse performance score and the vitals above, so scoring it too
    would penalise one slow page three times over.
    """
    data = _psi(ctx)
    if not data:
        return _unavailable("pagespeed_opportunities", "PageSpeed opportunities", ctx)

    opportunities = data.get("opportunities") or []
    if not opportunities:
        return CheckResult(
            "pagespeed_opportunities", CATEGORY, "info", 100, "PageSpeed opportunities",
            "Lighthouse found no significant optimisations left on this page.",
            value=[],
        )

    top = opportunities[0]
    saving = (
        f"{top['savings_ms']}ms"
        if top["savings_ms"]
        else f"{round(top['savings_bytes'] / 1024)}KB"
    )
    return CheckResult(
        "pagespeed_opportunities", CATEGORY, "info", 100, "PageSpeed opportunities",
        f"Lighthouse suggests {len(opportunities)} optimisation"
        f"{'s' if len(opportunities) > 1 else ''}, the largest being "
        f"\"{top['title']}\" (~{saving}).",
        value=opportunities,
        recommendation="Work down this list in order; it is sorted by estimated impact.",
    )


def check_lighthouse_categories(ctx: AnalysisContext) -> CheckResult:
    """Lighthouse accessibility / best-practices / SEO scores.

    Reported but not scored. Folding an accessibility score into the overall
    number would mean a report run with a PSI key and one run without were no
    longer comparable, and accessibility deserves its own treatment rather
    than being averaged into a performance category.
    """
    data = _psi(ctx)
    scores = {
        name: value
        for name, value in ((data or {}).get("scores") or {}).items()
        if name != "performance" and value is not None
    }
    if not scores:
        return _unavailable("lighthouse_categories", "Lighthouse audits", ctx)

    labels = {"accessibility": "Accessibility", "best-practices": "Best practices",
              "seo": "SEO"}
    summary = ", ".join(f"{labels.get(k, k)} {v}/100" for k, v in scores.items())
    weakest = min(scores.items(), key=lambda kv: kv[1])
    return CheckResult(
        "lighthouse_categories", CATEGORY, "info", 100, "Lighthouse audits",
        f"Lighthouse also scored this page: {summary}.",
        value=scores,
        recommendation=(
            f"{labels.get(weakest[0], weakest[0])} is the weakest at {weakest[1]}/100."
            if weakest[1] < LIGHTHOUSE_GOOD else None
        ),
    )


# The checks that read only ``ctx.extra["psi"]``, so they can be re-run once a
# PageSpeed result arrives after the rest of the page was analyzed.
PSI_CHECKS = [
    check_core_web_vitals,
    check_field_vitals,
    check_lighthouse_performance,
    check_pagespeed_opportunities,
    check_lighthouse_categories,
]

CHECKS = [
    check_ttfb,
    check_load_time,
    check_page_size,
    check_compression,
    check_render_blocking,
    *PSI_CHECKS,
]
