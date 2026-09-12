"""Heading structure checks (H1 presence + hierarchy)."""
from app.seo.types import AnalysisContext, CheckResult

CATEGORY = "structure"


def check_h1(ctx: AnalysisContext) -> CheckResult:
    h1s = ctx.soup.find_all("h1")
    count = len(h1s)
    text = h1s[0].get_text(strip=True) if h1s else ""
    if count == 1 and len(text) >= 10:
        return CheckResult(
            "h1_heading", CATEGORY, "good", 100, "H1 heading",
            "Exactly one descriptive H1 found.", value={"count": 1, "text": text},
        )
    if count == 0:
        return CheckResult(
            "h1_heading", CATEGORY, "critical", 0, "H1 heading",
            "No H1 heading found.", value={"count": 0},
            recommendation="Add a single, descriptive H1 to the page.",
        )
    if count > 1:
        return CheckResult(
            "h1_heading", CATEGORY, "warning", 60, "H1 heading",
            f"Found {count} H1 tags; a single H1 is recommended.",
            value={"count": count},
            recommendation="Use one H1 and demote the rest to H2/H3.",
        )
    return CheckResult(
        "h1_heading", CATEGORY, "warning", 70, "H1 heading",
        "H1 is present but very short.", value={"count": 1, "text": text},
        recommendation="Make the H1 more descriptive (>= 10 characters).",
    )


def check_heading_hierarchy(ctx: AnalysisContext) -> CheckResult:
    headings = ctx.soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    levels = [int(h.name[1]) for h in headings]
    counts = {f"h{i}": sum(1 for level in levels if level == i) for i in range(1, 7)}

    if not levels:
        return CheckResult(
            "heading_hierarchy", CATEGORY, "warning", 40, "Heading structure",
            "No headings found on the page.", value=counts,
            recommendation="Structure content with H1-H3 headings.",
        )

    # Flag a level being skipped (e.g. H2 -> H4 with no H3 between).
    skips = sum(
        1 for prev, cur in zip(levels, levels[1:], strict=False) if cur - prev > 1
    )
    if skips == 0:
        return CheckResult(
            "heading_hierarchy", CATEGORY, "good", 100, "Heading structure",
            "Heading levels are well structured.", value=counts,
        )
    return CheckResult(
        "heading_hierarchy", CATEGORY, "warning", 70, "Heading structure",
        f"Heading levels are skipped {skips} time(s).", value=counts,
        recommendation="Avoid jumping heading levels (e.g. H2 directly to H4).",
    )


CHECKS = [check_h1, check_heading_hierarchy]
