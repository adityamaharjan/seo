"""Page discovery for a site audit.

A site audit needs a list of URLs before it can analyze anything. Two sources
are used, in order of trustworthiness:

1. **Sitemaps.** A site that publishes one has told us which pages it considers
   worth indexing, which is a far better sample than whatever the homepage
   happens to link to. Sitemap indexes are expanded one level.
2. **Internal links.** Falling back to a breadth-first walk from the start URL,
   so a site without a sitemap is still auditable.

Every candidate is filtered the same way: same host, crawlable per robots.txt,
and re-checked by :mod:`app.seo.urlguard` before any request, because a page we
fetched can link anywhere including back into the private network.
"""
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.logging import get_logger
from app.seo import urlguard
from app.seo.robots import RobotsTxt, path_of

logger = get_logger(__name__)

# Query parameters that identify a campaign rather than a page. Left in, the
# same article arrives several times under different tracking tags and eats the
# page budget.
_TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "msclkid")

# Extensions that are never an HTML page worth auditing.
_NON_PAGE_SUFFIXES = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".css",
    ".js", ".json", ".xml", ".zip", ".gz", ".mp4", ".mp3", ".avi", ".woff",
    ".woff2", ".ttf", ".eot", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
)


@dataclass
class SiteSignals:
    """Host-level facts shared by every page in one audit."""

    base: str
    robots_txt: str | None = None
    robots: RobotsTxt = field(default_factory=lambda: RobotsTxt([], []))
    sitemap_found: bool = False
    sitemap_urls: list[str] = field(default_factory=list)

    def as_page_signals(self) -> dict:
        """The subset :func:`app.seo.analyzer.analyze` needs per page."""
        return {"robots_txt": self.robots_txt, "sitemap_found": self.sitemap_found}

    def allows(self, url: str) -> bool:
        return self.robots.allows(path_of(url), settings.SEO_USER_AGENT)


def normalize(url: str) -> str:
    """Canonical form used for deduplication.

    Fragments never identify a distinct page, tracking parameters identify a
    campaign, and a trailing slash is almost always the same document. Folding
    those together stops one page consuming several slots of the page budget.
    """
    url, _ = urldefrag(url)
    parts = urlparse(url)
    query = "&".join(
        piece
        for piece in parts.query.split("&")
        if piece and not piece.lower().startswith(_TRACKING_PARAMS)
    )
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    netloc = parts.netloc.lower()
    # Default ports are not part of a page's identity.
    for scheme, port in (("http", ":80"), ("https", ":443")):
        if parts.scheme == scheme and netloc.endswith(port):
            netloc = netloc[: -len(port)]
    return urlunparse((parts.scheme, netloc, path, "", query, ""))


def is_page_url(url: str) -> bool:
    """Whether a URL plausibly points at an HTML page rather than an asset."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        return False
    return not parts.path.lower().endswith(_NON_PAGE_SUFFIXES)


def same_site(url: str, host: str) -> bool:
    """Same host, ignoring a leading ``www.`` on either side.

    A crawl that treats ``example.com`` and ``www.example.com`` as different
    sites stops at the first canonical redirect.
    """
    def bare(value: str) -> str:
        return value.lower().removeprefix("www.")

    return bare(urlparse(url).netloc) == bare(host)


async def _guarded_get(client: httpx.AsyncClient, url: str) -> httpx.Response | None:
    """GET a URL, re-checking the SSRF guard on the initial hop and each redirect."""
    target = url
    for _ in range(settings.SEO_MAX_REDIRECTS):
        await urlguard.check_url(target)
        response = await client.get(target)
        urlguard.assert_peer_public(response)
        if response.has_redirect_location and response.next_request is not None:
            target = str(response.next_request.url)
            continue
        return response
    return None


async def load_site_signals(client: httpx.AsyncClient, start_url: str) -> SiteSignals:
    """Fetch and parse robots.txt once for the whole audit."""
    parts = urlparse(start_url)
    base = f"{parts.scheme}://{parts.netloc}"
    signals = SiteSignals(base=base)

    try:
        response = await _guarded_get(client, urljoin(base + "/", "robots.txt"))
    except (httpx.HTTPError, urlguard.BlockedURLError):
        response = None
    if response is not None and response.status_code < 400:
        signals.robots_txt = response.text
        signals.robots = RobotsTxt.parse(response.text)

    # Sitemaps declared in robots.txt win; /sitemap.xml is the conventional
    # fallback for the many sites that publish one without announcing it.
    declared = [u for u in signals.robots.sitemaps if same_site(u, parts.netloc)]
    signals.sitemap_urls = declared or [urljoin(base + "/", "sitemap.xml")]
    return signals


def _parse_sitemap(body: bytes) -> tuple[list[str], bool]:
    """Extract ``<loc>`` values and say whether this was a sitemap index."""
    soup = BeautifulSoup(body, "xml")
    is_index = soup.find("sitemapindex") is not None
    return [loc.get_text(strip=True) for loc in soup.find_all("loc")], is_index


async def urls_from_sitemaps(
    client: httpx.AsyncClient, signals: SiteSignals, *, limit: int
) -> list[str]:
    """Collect page URLs from the site's sitemaps, expanding one index level."""
    host = urlparse(signals.base).netloc
    queue = list(signals.sitemap_urls)
    seen_sitemaps: set[str] = set()
    found: list[str] = []
    seen_pages: set[str] = set()

    while queue and len(found) < limit and len(seen_sitemaps) < settings.SITE_AUDIT_MAX_SITEMAPS:
        sitemap_url = queue.pop(0)
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)
        try:
            response = await _guarded_get(client, sitemap_url)
        except (httpx.HTTPError, urlguard.BlockedURLError):
            continue
        if response is None or response.status_code >= 400 or not response.content:
            continue

        try:
            locs, is_index = _parse_sitemap(response.content)
        except Exception:  # a malformed sitemap must not abort the audit
            logger.warning("sitemap parse failed", extra={"url": sitemap_url})
            continue

        signals.sitemap_found = True
        if is_index:
            queue.extend(loc for loc in locs if same_site(loc, host))
            continue
        for loc in locs:
            canonical = normalize(loc)
            if (
                canonical in seen_pages
                or not same_site(canonical, host)
                or not is_page_url(canonical)
                or not signals.allows(canonical)
            ):
                continue
            seen_pages.add(canonical)
            found.append(canonical)
            if len(found) >= limit:
                break
    return found


def links_worth_following(
    links: list[str], signals: SiteSignals, host: str, seen: set[str]
) -> list[str]:
    """Filter one page's internal links down to new, crawlable page URLs."""
    out: list[str] = []
    for link in links:
        canonical = normalize(link)
        if (
            canonical in seen
            or not same_site(canonical, host)
            or not is_page_url(canonical)
            or not signals.allows(canonical)
        ):
            continue
        seen.add(canonical)
        out.append(canonical)
    return out
