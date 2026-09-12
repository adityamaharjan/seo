"""Async HTTP fetcher that records real transfer timing.

We stream the response so we can measure true time-to-first-byte (the wait
before the first body chunk arrives) separately from the total download time.

Redirects are followed manually rather than by httpx, so that every hop is
re-checked by :mod:`app.seo.urlguard`. Letting the client follow redirects
would allow a public URL to bounce the fetch into the private network.
"""
import time
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.seo import urlguard
from app.seo.types import FetchResult

logger = get_logger(__name__)


def _failed(url: str, domain: str, error: str, status_code: int = 0) -> FetchResult:
    return FetchResult(
        requested_url=url,
        final_url=url,
        domain=domain,
        status_code=status_code,
        ok=False,
        content=b"",
        text="",
        headers={},
        ttfb_ms=None,
        load_time_ms=None,
        transfer_size_bytes=0,
        html_size_bytes=0,
        compressed=False,
        redirect_count=0,
        error=error,
    )


async def fetch(url: str) -> FetchResult:
    domain = urlparse(url).netloc
    # Accept-Encoding is deliberately left to httpx, which advertises exactly the
    # codecs it can actually decode. Hard-coding it once promised brotli without
    # the decoder installed, so every br-serving site (i.e. anything behind
    # Cloudflare) came back as raw compressed bytes: no title, no headings, and
    # binary noise where the text should be.
    headers = {
        "User-Agent": settings.SEO_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    start = time.perf_counter()
    current_url = url
    redirect_count = 0

    try:
        async with httpx.AsyncClient(
            http2=True,
            follow_redirects=False,
            timeout=settings.SEO_TIMEOUT_SECONDS,
            verify=True,
        ) as client:
            while True:
                # Layers 1 and 2 of the SSRF guard, re-applied on every hop.
                await urlguard.check_url(current_url)

                async with client.stream(
                    "GET", current_url, headers=headers
                ) as response:
                    # Layer 3: the address actually connected to.
                    urlguard.assert_peer_public(response)

                    if (
                        response.has_redirect_location
                        and response.next_request is not None
                    ):
                        if redirect_count >= settings.SEO_MAX_REDIRECTS:
                            return _failed(
                                url, domain, "Too many redirects.",
                                status_code=response.status_code,
                            )
                        current_url = str(response.next_request.url)
                        redirect_count += 1
                        continue

                    ttfb_ms: float | None = None
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        if ttfb_ms is None:
                            ttfb_ms = round((time.perf_counter() - start) * 1000, 1)
                        total += len(chunk)
                        chunks.append(chunk)
                        if total > settings.SEO_MAX_PAGE_BYTES:
                            # Stop reading oversized pages; analyze what we have.
                            break

                    load_time_ms = round((time.perf_counter() - start) * 1000, 1)
                    content = b"".join(chunks)
                    final_url = str(response.url)
                    resp_headers = {k.lower(): v for k, v in response.headers.items()}
                    response_text = content.decode(
                        response.encoding or "utf-8", errors="replace"
                    )

                    return FetchResult(
                        requested_url=url,
                        final_url=final_url,
                        domain=urlparse(final_url).netloc or domain,
                        status_code=response.status_code,
                        ok=response.status_code < 400,
                        content=content,
                        text=response_text,
                        headers=resp_headers,
                        ttfb_ms=ttfb_ms,
                        load_time_ms=load_time_ms,
                        transfer_size_bytes=total,
                        html_size_bytes=len(content),
                        compressed="content-encoding" in resp_headers,
                        redirect_count=redirect_count,
                    )
    except urlguard.BlockedURLError as exc:
        logger.warning("fetch blocked", extra={"url": url, "reason": str(exc)})
        return _failed(url, domain, str(exc))
    except httpx.HTTPError as exc:
        logger.warning("fetch failed", extra={"url": url, "error": str(exc)})
        return _failed(url, domain, str(exc))


async def head_ok(client: httpx.AsyncClient, url: str) -> bool:
    """Return True if a URL responds with a non-error status.

    Used for broken-link sampling, where the URLs come from the analyzed page
    and are therefore attacker-controlled: the guard applies here too, and a
    blocked target is reported as broken rather than being fetched.
    """
    hops = 0
    current = url
    try:
        while True:
            await urlguard.check_url(current)
            resp = await client.head(current, follow_redirects=False)
            if resp.status_code == 405 or (
                resp.status_code >= 400 and not resp.has_redirect_location
            ):
                # Some servers reject HEAD; retry once with a ranged GET.
                resp = await client.get(
                    current, headers={"Range": "bytes=0-0"}, follow_redirects=False
                )
            if resp.has_redirect_location and resp.next_request is not None:
                if hops >= 5:
                    return False
                current = str(resp.next_request.url)
                hops += 1
                continue
            urlguard.assert_peer_public(resp)
            return resp.status_code < 400
    except (httpx.HTTPError, urlguard.BlockedURLError):
        return False
