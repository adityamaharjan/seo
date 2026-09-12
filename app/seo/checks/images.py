"""Image checks: alt text, dimensions, lazy-loading, next-gen formats."""
from app.seo.types import AnalysisContext, CheckResult

CATEGORY = "content"
_NEXT_GEN = (".webp", ".avif")


def check_image_alt(ctx: AnalysisContext) -> CheckResult:
    imgs = ctx.soup.find_all("img")
    if not imgs:
        return CheckResult(
            "image_alt", CATEGORY, "info", 100, "Image alt text",
            "No images on the page.", value={"total": 0},
        )
    missing = [img.get("src", "?") for img in imgs if not (img.get("alt") or "").strip()]
    total = len(imgs)
    if not missing:
        return CheckResult(
            "image_alt", CATEGORY, "good", 100, "Image alt text",
            f"All {total} images have alt text.", value={"total": total, "missing": 0},
        )
    ratio = len(missing) / total
    score = max(0, round(100 * (1 - ratio)))
    status = "critical" if ratio > 0.5 else "warning"
    return CheckResult(
        "image_alt", CATEGORY, status, score, "Image alt text",
        f"{len(missing)} of {total} images are missing alt text.",
        value={"total": total, "missing": len(missing), "examples": missing[:10]},
        recommendation="Add descriptive alt attributes to all meaningful images.",
    )


def check_image_optimization(ctx: AnalysisContext) -> CheckResult:
    imgs = ctx.soup.find_all("img")
    if not imgs:
        return CheckResult(
            "image_optimization", CATEGORY, "info", 100, "Image optimization",
            "No images on the page.", value={"total": 0},
        )
    total = len(imgs)
    lazy = sum(1 for i in imgs if (i.get("loading") or "").lower() == "lazy")
    no_dims = sum(1 for i in imgs if not i.get("width") or not i.get("height"))
    next_gen = sum(
        1 for i in imgs if (i.get("src", "").lower()).endswith(_NEXT_GEN)
    )
    score = 100
    if no_dims:
        score -= min(40, round(40 * no_dims / total))
    if lazy == 0 and total > 3:
        score -= 15
    status = "good" if score >= 85 else "warning"
    return CheckResult(
        "image_optimization", CATEGORY, status, max(0, score), "Image optimization",
        f"{lazy}/{total} lazy-loaded, {no_dims} missing dimensions, "
        f"{next_gen} next-gen format.",
        value={
            "total": total,
            "lazy_loaded": lazy,
            "missing_dimensions": no_dims,
            "next_gen_format": next_gen,
        },
        recommendation=(
            "Set width/height to avoid layout shift and lazy-load offscreen images."
            if status != "good" else None
        ),
    )


CHECKS = [check_image_alt, check_image_optimization]
