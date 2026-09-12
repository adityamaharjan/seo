"""Link checks: internal/external counts, anchor quality, nofollow.

Broken-link detection is performed asynchronously in the analyzer and the
result is injected via ``ctx.broken_links``.
"""
from urllib.parse import urljoin, urlparse

from app.seo.types import AnalysisContext, CheckResult

CATEGORY = "links"

_GENERIC_ANCHORS = {"click here", "here", "read more", "more", "link", "this"}


def classify_links(ctx: AnalysisContext) -> tuple[list[str], list[str]]:
    """Split anchors into internal/external and cache them on ``ctx.extra``.

    Idempotent: safe to call from the analyzer (to seed broken-link sampling)
    and again from :func:`check_links`.
    """
    domain = ctx.fetch.domain
    internal, external = [], []
    for a in ctx.soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(ctx.fetch.final_url, href)
        host = urlparse(absolute).netloc
        if host == domain or host == "":
            internal.append(absolute)
        elif absolute.startswith("http"):
            external.append(absolute)
    ctx.extra["internal_links"] = internal
    ctx.extra["external_links"] = external
    return internal, external


def check_links(ctx: AnalysisContext) -> CheckResult:
    internal, external = classify_links(ctx)
    n_int, n_ext = len(internal), len(external)
    if n_int == 0:
        status, score, msg = "warning", 50, "No internal links found."
        rec = "Add internal links to help crawlers and users navigate."
    else:
        status, score, msg = "good", 100, f"{n_int} internal and {n_ext} external links."
        rec = None
    return CheckResult(
        "links", CATEGORY, status, score, "Link profile", msg,
        value={"internal": n_int, "external": n_ext},
        recommendation=rec,
    )


def check_anchor_quality(ctx: AnalysisContext) -> CheckResult:
    anchors = ctx.soup.find_all("a", href=True)
    generic = [
        a.get_text(strip=True)
        for a in anchors
        if a.get_text(strip=True).lower() in _GENERIC_ANCHORS
    ]
    empty = sum(
        1 for a in anchors if not a.get_text(strip=True) and not a.find("img")
    )
    issues = len(generic) + empty
    if issues == 0:
        return CheckResult(
            "anchor_quality", CATEGORY, "good", 100, "Anchor text",
            "Anchor text is descriptive.", value={"generic": 0, "empty": 0},
        )
    return CheckResult(
        "anchor_quality", CATEGORY, "warning", 70, "Anchor text",
        f"{len(generic)} generic and {empty} empty anchors found.",
        value={"generic": len(generic), "empty": empty},
        recommendation="Use descriptive anchor text instead of 'click here'.",
    )


def check_broken_links(ctx: AnalysisContext) -> CheckResult:
    if ctx.broken_links is None:
        return CheckResult(
            "broken_links", CATEGORY, "info", 100, "Broken links",
            "Broken-link check was not run.", value=None,
        )
    n = len(ctx.broken_links)
    if n == 0:
        return CheckResult(
            "broken_links", CATEGORY, "good", 100, "Broken links",
            "No broken links detected in the sampled set.", value=[],
        )
    status = "critical" if n >= 5 else "warning"
    return CheckResult(
        "broken_links", CATEGORY, status, max(0, 100 - n * 15), "Broken links",
        f"{n} broken link(s) detected.", value=ctx.broken_links[:20],
        recommendation="Fix or remove links returning 4xx/5xx responses.",
    )


CHECKS = [check_links, check_anchor_quality, check_broken_links]
