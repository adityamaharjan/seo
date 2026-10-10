"""Technical / mobile checks: viewport, charset, doctype, favicon, HTTPS."""
from app.seo.types import AnalysisContext, CheckResult
from app.seo.text import attr


def check_viewport(ctx: AnalysisContext) -> CheckResult:
    tag = ctx.soup.find("meta", attrs={"name": "viewport"})
    if content := attr(tag, "content").strip():
        return CheckResult(
            "mobile_viewport", "mobile", "good", 100, "Mobile viewport",
            "Responsive viewport meta tag present.", value=content,
        )
    return CheckResult(
        "mobile_viewport", "mobile", "critical", 0, "Mobile viewport",
        "Missing viewport meta tag.", value=None,
        recommendation='Add <meta name="viewport" content="width=device-width, initial-scale=1">.',
    )


def check_charset(ctx: AnalysisContext) -> CheckResult:
    has = ctx.soup.find("meta", attrs={"charset": True}) or ctx.soup.find(
        "meta", attrs={"http-equiv": lambda v: v is not None and v.lower() == "content-type"}
    )
    if has:
        return CheckResult(
            "charset", "structure", "good", 100, "Character encoding",
            "Character encoding is declared.", value=True,
        )
    return CheckResult(
        "charset", "structure", "warning", 60, "Character encoding",
        "No charset declaration found.", value=False,
        recommendation='Add <meta charset="utf-8"> early in <head>.',
    )


def check_doctype(ctx: AnalysisContext) -> CheckResult:
    head = ctx.fetch.text[:200].lower()
    if "<!doctype html>" in head:
        return CheckResult(
            "doctype", "structure", "good", 100, "Doctype",
            "HTML5 doctype declared.", value=True,
        )
    return CheckResult(
        "doctype", "structure", "warning", 60, "Doctype",
        "Missing or non-HTML5 doctype.", value=False,
        recommendation="Start the document with <!DOCTYPE html>.",
    )


def check_favicon(ctx: AnalysisContext) -> CheckResult:
    # A page can have a working favicon two ways: an explicit <link rel=icon>,
    # or (the common case for most sites) nothing at all, relying on the
    # browser's default /favicon.ico fallback. Both are resolved and verified
    # reachable by the analyzer beforehand; ctx.extra is empty for the
    # no-network unit tests, which correctly falls through to "not found".
    resolved = ctx.extra.get("favicon_url")
    declared = ctx.extra.get("favicon_declared", False)
    if resolved:
        msg = (
            "Favicon is declared and reachable."
            if declared
            else "No favicon link declared, but the default /favicon.ico resolves."
        )
        return CheckResult(
            "favicon", "structure", "good", 100, "Favicon", msg, value=resolved,
        )
    if declared:
        return CheckResult(
            "favicon", "structure", "warning", 50, "Favicon",
            "A favicon is declared but the file could not be fetched.", value=None,
            recommendation="Verify the favicon href points to a reachable file.",
        )
    return CheckResult(
        "favicon", "structure", "info", 80, "Favicon",
        "No favicon found (checked <link rel=icon> and the default /favicon.ico).",
        value=None,
        recommendation="Add a favicon for brand recognition in tabs/results.",
    )


def check_https(ctx: AnalysisContext) -> CheckResult:
    if ctx.fetch.final_url.startswith("https://"):
        return CheckResult(
            "https", "security", "good", 100, "HTTPS",
            "Served over a secure HTTPS connection.", value="https",
        )
    return CheckResult(
        "https", "security", "critical", 0, "HTTPS",
        "Page is not served over HTTPS.", value="http",
        recommendation="Serve the site over HTTPS with a valid TLS certificate.",
    )


CHECKS = [check_viewport, check_charset, check_doctype, check_favicon, check_https]
