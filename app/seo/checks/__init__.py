"""Registry of all synchronous check functions.

Each check is a callable ``(AnalysisContext) -> CheckResult``. Async network
work (robots.txt, sitemap, broken links) is handled by the analyzer before
these run.

Keyword targeting is deliberately absent: it is a separate feature living in
:mod:`app.seo.keywords`, because it scores user-supplied intent rather than the
health of the URL itself.
"""
from app.seo.checks import (
    content,
    headings,
    images,
    indexability,
    links,
    meta,
    performance,
    security,
    structured_data,
    technical,
)

ALL_CHECKS = [
    *meta.CHECKS,
    *structured_data.CHECKS,
    *headings.CHECKS,
    *content.CHECKS,
    *images.CHECKS,
    *links.CHECKS,
    *indexability.CHECKS,
    *performance.CHECKS,
    *technical.CHECKS,
    *security.CHECKS,
]
