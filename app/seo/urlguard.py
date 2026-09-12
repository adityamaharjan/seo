"""SSRF guard: refuse to fetch anything that is not a public internet host.

The analysis endpoint accepts an arbitrary URL from an authenticated but
otherwise untrusted user, and the server then fetches it and returns what it
found. Without this guard the API is an open proxy into whatever network the
server sits on: cloud metadata endpoints, loopback services, and RFC1918 hosts
would all be reachable.

Three layers are applied, because each one alone is bypassable:

1. :func:`validate_url` rejects non-HTTP schemes, missing hosts, and hosts that
   are written as literal non-public IP addresses.
2. :func:`resolve_and_validate` resolves the hostname and rejects it when *any*
   returned address is non-public (a name with mixed public/private records
   must not be trusted).
3. :func:`assert_peer_public` inspects the address the socket actually
   connected to, which closes the DNS-rebinding window between resolution and
   connection.

Redirects must be followed manually so that every hop passes all three layers;
see :mod:`app.seo.fetcher`.
"""
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import settings

ALLOWED_SCHEMES = frozenset({"http", "https"})

DNS_TIMEOUT_SECONDS = 5.0

# Ports that are almost certainly an internal service rather than a website.
# Blocking them stops the guard being used as a port scanner even when the
# target host is genuinely public.
BLOCKED_PORTS = frozenset(
    {22, 23, 25, 110, 143, 445, 465, 587, 993, 995, 1433, 3306, 3389, 5432, 5672,
     6379, 9200, 11211, 27017}
)


class BlockedURLError(Exception):
    """Raised when a URL points somewhere the fetcher must not go."""


def _ip_is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True only for globally routable unicast addresses."""
    # An IPv4 address embedded in IPv6 (``::ffff:127.0.0.1``) must be judged on
    # the IPv4 address it carries.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _parse_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Return the address if ``host`` is written as an IP literal, else None."""
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None


def validate_url(url: str) -> tuple[str, str, int]:
    """Layer 1. Return ``(scheme, host, port)`` or raise :class:`BlockedURLError`."""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise BlockedURLError(f"Only http and https URLs can be analyzed, not '{scheme}'.")

    host = parsed.hostname
    if not host:
        raise BlockedURLError("URL has no host.")

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:  # out-of-range port in the URL
        raise BlockedURLError("URL has an invalid port.") from exc

    if settings.SEO_ALLOW_PRIVATE_TARGETS:
        return scheme, host, port

    if port in BLOCKED_PORTS:
        raise BlockedURLError(f"Port {port} is not an allowed web port.")

    literal = _parse_ip(host)
    if literal is not None and not _ip_is_public(literal):
        raise BlockedURLError(f"'{host}' is not a public address.")

    return scheme, host, port


async def resolve_and_validate(host: str, port: int) -> list[str]:
    """Layer 2. Resolve ``host`` and reject it if any address is non-public."""
    if settings.SEO_ALLOW_PRIVATE_TARGETS:
        return []

    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, port, type=socket.SOCK_STREAM),
            timeout=DNS_TIMEOUT_SECONDS,
        )
    except (socket.gaierror, TimeoutError) as exc:
        raise BlockedURLError(f"Could not resolve '{host}'.") from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise BlockedURLError(f"Could not resolve '{host}'.")

    for address in addresses:
        ip = _parse_ip(address)
        if ip is None or not _ip_is_public(ip):
            raise BlockedURLError(f"'{host}' resolves to a non-public address.")
    return sorted(addresses)


async def check_url(url: str) -> None:
    """Run layers 1 and 2 for ``url``."""
    _, host, port = validate_url(url)
    await resolve_and_validate(host, port)


def assert_peer_public(response) -> None:
    """Layer 3. Verify the address the connection actually landed on.

    Guards against DNS rebinding, where a name resolves to a public address
    during validation and a private one microseconds later at connect time.
    """
    if settings.SEO_ALLOW_PRIVATE_TARGETS:
        return

    stream = response.extensions.get("network_stream")
    if stream is None:  # e.g. a mocked transport in tests
        return
    try:
        peer = stream.get_extra_info("server_addr")
    except Exception:  # transport does not expose it; layers 1-2 still applied
        return
    if not peer:
        return

    ip = _parse_ip(str(peer[0]))
    if ip is not None and not _ip_is_public(ip):
        raise BlockedURLError(f"Connection resolved to a non-public address ({peer[0]}).")
