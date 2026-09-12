"""Meta / head-tag checks: title, description, canonical, meta-robots, lang."""
from urllib.parse import urlparse

from app.seo.constants import DESC_MAX, DESC_MIN, TITLE_MAX, TITLE_MIN, TITLE_PIXEL_SAFE_MAX
from app.seo.types import AnalysisContext, CheckResult

CATEGORY = "meta"


def check_title(ctx: AnalysisContext) -> CheckResult:
    tag = ctx.soup.find("title")
    title = tag.get_text(strip=True) if tag else ""
    length = len(title)
    if not title:
        return CheckResult(
            "title_tag", CATEGORY, "critical", 0, "Title tag", "No title tag found.",
            value=None,
            recommendation="Add a unique <title> of 30-60 characters.",
        )
    if TITLE_MIN <= length <= TITLE_MAX:
        status, score, msg = "good", 100, "Title length is optimal."
    elif TITLE_MAX < length <= TITLE_PIXEL_SAFE_MAX:
        status, score, msg = "good", 90, "Title length is acceptable."
    elif length < TITLE_MIN:
        status, score, msg = "warning", 60, "Title is shorter than recommended."
    else:
        status, score, msg = "warning", 55, "Title is longer than recommended and may be truncated."
    return CheckResult(
        "title_tag", CATEGORY, status, score, "Title tag", msg,
        value={"title": title, "length": length},
        recommendation=None if status == "good" else "Aim for 30-60 characters.",
    )


def check_meta_description(ctx: AnalysisContext) -> CheckResult:
    tag = ctx.soup.find("meta", attrs={"name": "description"})
    desc = (tag.get("content") or "").strip() if tag else ""
    length = len(desc)
    if not desc:
        return CheckResult(
            "meta_description", CATEGORY, "critical", 0, "Meta description",
            "Missing meta description.", value=None,
            recommendation="Add a compelling 70-160 character meta description.",
        )
    if DESC_MIN <= length <= DESC_MAX:
        status, score, msg = "good", 100, "Meta description length is optimal."
    elif length < DESC_MIN:
        status, score, msg = "warning", 65, "Meta description is shorter than recommended."
    else:
        status, score, msg = "warning", 60, "Meta description may be truncated in results."
    return CheckResult(
        "meta_description", CATEGORY, status, score, "Meta description", msg,
        value={"description": desc, "length": length},
        recommendation=None if status == "good" else "Aim for 70-160 characters.",
    )


def check_canonical(ctx: AnalysisContext) -> CheckResult:
    tag = ctx.soup.find("link", attrs={"rel": lambda v: v and "canonical" in v})
    href = (tag.get("href") or "").strip() if tag else ""
    if not href:
        return CheckResult(
            "canonical", CATEGORY, "warning", 50, "Canonical URL",
            "No canonical link found.", value=None,
            recommendation="Add <link rel=\"canonical\"> to avoid duplicate-content issues.",
        )
    same = urlparse(href).path.rstrip("/") == urlparse(ctx.fetch.final_url).path.rstrip("/")
    return CheckResult(
        "canonical", CATEGORY, "good", 100, "Canonical URL",
        "Canonical URL is set." + ("" if same else " (points to a different path)."),
        value={"canonical": href, "self_referencing": same},
    )


def check_meta_robots(ctx: AnalysisContext) -> CheckResult:
    """Indexability as declared by the page, via either channel.

    A noindex can arrive in the meta tag or in an ``X-Robots-Tag`` response
    header, and search engines honour both equally. Reading only the tag missed
    every page whose CMS or CDN sets the header instead.
    """
    tag = ctx.soup.find("meta", attrs={"name": lambda v: v and v.lower() == "robots"})
    meta_content = (tag.get("content") or "").lower().strip() if tag else ""
    header_content = ctx.fetch.headers.get("x-robots-tag", "").lower().strip()

    sources = {"meta": meta_content or None, "header": header_content or None}
    noindex_in = [name for name, value in sources.items() if value and "noindex" in value]
    if noindex_in:
        where = "a meta robots tag" if noindex_in == ["meta"] else "an X-Robots-Tag header"
        if len(noindex_in) == 2:
            where = "both a meta robots tag and an X-Robots-Tag header"
        return CheckResult(
            "meta_robots", CATEGORY, "critical", 0, "Meta robots",
            f"Page is marked noindex by {where} and will be excluded from search results.",
            value=sources,
            recommendation="Remove 'noindex' if this page should rank.",
        )

    declared = "; ".join(value for value in sources.values() if value)
    return CheckResult(
        "meta_robots", CATEGORY, "good", 100, "Meta robots",
        "Page is indexable." if not declared else f"Robots directive: {declared}",
        value=sources if declared else "index, follow (default)",
    )


def check_lang(ctx: AnalysisContext) -> CheckResult:
    html_tag = ctx.soup.find("html")
    lang = (html_tag.get("lang") or "").strip() if html_tag else ""
    if lang:
        return CheckResult(
            "html_lang", CATEGORY, "good", 100, "Language declaration",
            f"Document language declared as '{lang}'.", value=lang,
        )
    return CheckResult(
        "html_lang", CATEGORY, "warning", 50, "Language declaration",
        "Missing lang attribute on <html>.", value=None,
        recommendation="Add lang=\"...\" to <html> for accessibility and SEO.",
    )


CHECKS = [check_title, check_meta_description, check_canonical, check_meta_robots, check_lang]
