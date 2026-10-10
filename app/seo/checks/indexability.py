"""Indexability checks: robots.txt, sitemap, hreflang.

robots.txt and sitemap presence are fetched asynchronously by the analyzer and
injected via ``ctx.robots_txt`` / ``ctx.sitemap_found``.
"""
from app.seo.robots import RobotsTxt, path_of
from app.seo.types import AnalysisContext, CheckResult
from app.seo.text import attr

CATEGORY = "indexability"

# The agent whose access actually decides whether this page can rank. Checked
# alongside the wildcard group because a file can welcome everyone in general
# and still single Google out.
_SEARCH_AGENT = "Googlebot"


def check_robots_txt(ctx: AnalysisContext) -> CheckResult:
    if ctx.robots_txt is None:
        return CheckResult(
            "robots_txt", CATEGORY, "warning", 60, "robots.txt",
            "robots.txt not found or unreachable.", value=None,
            recommendation="Add a robots.txt to guide crawlers and reference your sitemap.",
        )

    robots = RobotsTxt.parse(ctx.robots_txt)
    path = path_of(ctx.fetch.final_url)
    # Blocking named scrapers is normal and healthy, so only the wildcard group
    # and Googlebot's own group can fail this check.
    site_blocked = robots.blocks_entire_site("*")
    page_blocked = not robots.allows(path, "*")
    google_blocked = not robots.allows(path, _SEARCH_AGENT)
    other_agents = robots.blocked_agents()

    detail = {
        "sitemap_reference": bool(robots.sitemaps),
        "sitemaps": robots.sitemaps[:10],
        "blocked_agents": other_agents,
        "path_checked": path,
    }

    if site_blocked:
        return CheckResult(
            "robots_txt", CATEGORY, "critical", 0, "robots.txt",
            "robots.txt disallows every crawler from the entire site.",
            value=detail,
            recommendation="Remove the site-wide 'Disallow: /' from the 'User-agent: *' group.",
        )
    if page_blocked or google_blocked:
        who = "all crawlers" if page_blocked else "Googlebot"
        return CheckResult(
            "robots_txt", CATEGORY, "critical", 0, "robots.txt",
            f"robots.txt blocks {who} from crawling this page ({path}).",
            value=detail,
            recommendation=f"Remove the rule in robots.txt that disallows {path}.",
        )

    message = "robots.txt found" + (
        " with a sitemap reference." if robots.sitemaps else ", but it references no sitemap."
    )
    if other_agents:
        message += f" It blocks {len(other_agents)} named crawler(s), which does not affect search."
    return CheckResult(
        "robots_txt", CATEGORY, "good" if robots.sitemaps else "warning",
        100 if robots.sitemaps else 80, "robots.txt", message, value=detail,
        recommendation=None if robots.sitemaps else "Reference your sitemap from robots.txt.",
    )


def check_sitemap(ctx: AnalysisContext) -> CheckResult:
    if ctx.sitemap_found:
        return CheckResult(
            "sitemap", CATEGORY, "good", 100, "XML sitemap",
            "XML sitemap is reachable.", value=True,
        )
    return CheckResult(
        "sitemap", CATEGORY, "warning", 50, "XML sitemap",
        "No sitemap.xml found at the site root.", value=False,
        recommendation="Publish a sitemap.xml and reference it in robots.txt.",
    )


def check_hreflang(ctx: AnalysisContext) -> CheckResult:
    tags = ctx.soup.find_all("link", attrs={"rel": "alternate", "hreflang": True})
    if tags:
        langs = [attr(t, "hreflang") for t in tags]
        return CheckResult(
            "hreflang", CATEGORY, "good", 100, "hreflang",
            f"hreflang annotations present for: {', '.join(langs)}.", value=langs,
        )
    return CheckResult(
        "hreflang", CATEGORY, "info", 90, "hreflang",
        "No hreflang annotations (only needed for multilingual sites).",
        value=None,
    )


CHECKS = [check_robots_txt, check_sitemap, check_hreflang]
