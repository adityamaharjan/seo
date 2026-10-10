"""Structured data checks: JSON-LD schema.org, Open Graph, Twitter cards."""
import json

from app.seo.types import AnalysisContext, CheckResult
from app.seo.text import attr

CATEGORY = "meta"


def check_json_ld(ctx: AnalysisContext) -> CheckResult:
    scripts = ctx.soup.find_all("script", attrs={"type": "application/ld+json"})
    types: list[str] = []
    invalid = 0
    for s in scripts:
        try:
            data = json.loads(s.string or "{}")
        except (json.JSONDecodeError, TypeError):
            invalid += 1
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type"):
                t = item["@type"]
                types.extend(t if isinstance(t, list) else [t])
    if not scripts:
        return CheckResult(
            "structured_data", CATEGORY, "warning", 50, "Structured data",
            "No JSON-LD structured data found.", value=None,
            recommendation="Add schema.org JSON-LD to enable rich results.",
        )
    if invalid:
        return CheckResult(
            "structured_data", CATEGORY, "warning", 70, "Structured data",
            f"{invalid} structured-data block(s) contain invalid JSON.",
            value={"types": types, "invalid_blocks": invalid},
            recommendation="Fix malformed JSON-LD.",
        )
    return CheckResult(
        "structured_data", CATEGORY, "good", 100, "Structured data",
        f"Found structured data: {', '.join(types) or 'present'}.",
        value={"types": types},
    )


def check_open_graph(ctx: AnalysisContext) -> CheckResult:
    found = {
        attr(tag, "property"): attr(tag, "content")
        for tag in ctx.soup.find_all("meta", attrs={"property": True})
        if attr(tag, "property").startswith("og:")
    }
    required = {"og:title", "og:description", "og:image"}
    missing = sorted(required - set(found))
    if not found:
        return CheckResult(
            "open_graph", CATEGORY, "warning", 50, "Open Graph",
            "No Open Graph tags found.", value=None,
            recommendation="Add og:title, og:description and og:image for social sharing.",
        )
    if missing:
        return CheckResult(
            "open_graph", CATEGORY, "warning", 75, "Open Graph",
            f"Missing recommended OG tags: {', '.join(missing)}.",
            value={"present": list(found), "missing": missing},
            recommendation=f"Add {', '.join(missing)}.",
        )
    return CheckResult(
        "open_graph", CATEGORY, "good", 100, "Open Graph",
        "Core Open Graph tags are present.", value={"present": list(found)},
    )


def check_twitter_card(ctx: AnalysisContext) -> CheckResult:
    found = [
        attr(tag, "name")
        for tag in ctx.soup.find_all("meta", attrs={"name": True})
        if attr(tag, "name").startswith("twitter:")
    ]
    if found:
        return CheckResult(
            "twitter_card", CATEGORY, "good", 100, "Twitter card",
            "Twitter card tags present.", value=found,
        )
    return CheckResult(
        "twitter_card", CATEGORY, "info", 70, "Twitter card",
        "No Twitter card tags found.", value=None,
        recommendation="Optionally add twitter:card tags for richer Twitter previews.",
    )


CHECKS = [check_json_ld, check_open_graph, check_twitter_card]
