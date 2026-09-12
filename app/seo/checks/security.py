"""Security header checks and mixed-content detection."""
from app.seo.types import AnalysisContext, CheckResult

CATEGORY = "security"

_HEADERS = {
    "strict-transport-security": "HSTS",
    "content-security-policy": "Content-Security-Policy",
    "x-frame-options": "X-Frame-Options",
    "x-content-type-options": "X-Content-Type-Options",
    "referrer-policy": "Referrer-Policy",
}


def check_security_headers(ctx: AnalysisContext) -> CheckResult:
    present = [name for key, name in _HEADERS.items() if key in ctx.fetch.headers]
    missing = [name for key, name in _HEADERS.items() if key not in ctx.fetch.headers]
    score = round(100 * len(present) / len(_HEADERS))
    if not missing:
        status, msg = "good", "All recommended security headers are present."
    elif len(present) >= 3:
        status, msg = "good", f"Most security headers present; missing: {', '.join(missing)}."
    else:
        status, msg = "warning", f"Missing security headers: {', '.join(missing)}."
    return CheckResult(
        "security_headers", CATEGORY, status, score, "Security headers", msg,
        value={"present": present, "missing": missing},
        recommendation=None if status == "good" else "Add the missing security response headers.",
    )


def check_mixed_content(ctx: AnalysisContext) -> CheckResult:
    if not ctx.fetch.final_url.startswith("https://"):
        return CheckResult(
            "mixed_content", CATEGORY, "info", 100, "Mixed content",
            "Page is not HTTPS; mixed-content check skipped.", value=None,
        )
    insecure = []
    for tag, attr in (("img", "src"), ("script", "src"), ("link", "href")):
        for el in ctx.soup.find_all(tag):
            ref = el.get(attr, "")
            if ref.startswith("http://"):
                insecure.append(ref)
    if not insecure:
        return CheckResult(
            "mixed_content", CATEGORY, "good", 100, "Mixed content",
            "No insecure (http://) resources on the HTTPS page.", value=[],
        )
    return CheckResult(
        "mixed_content", CATEGORY, "critical", 40, "Mixed content",
        f"{len(insecure)} insecure resource(s) loaded over HTTP.",
        value=insecure[:15],
        recommendation="Load all subresources over HTTPS.",
    )


CHECKS = [check_security_headers, check_mixed_content]
