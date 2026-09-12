"""Tests for the SSRF guard.

These are the cases that made the analysis endpoint an open proxy into the
private network before the guard existed.
"""
import pytest

from app.seo import urlguard

BLOCKED = [
    "http://169.254.169.254/latest/meta-data/",   # cloud metadata
    "http://127.0.0.1/",                          # loopback
    "http://127.0.0.1:8001/api/v1/health",        # our own API
    "http://[::1]/",                              # IPv6 loopback
    "http://[::ffff:127.0.0.1]/",                 # IPv4-mapped loopback
    "http://10.0.0.5/admin",                      # RFC1918
    "http://172.16.4.4/",                         # RFC1918
    "http://192.168.1.1/",                        # RFC1918
    "http://0.0.0.0/",                            # unspecified
    "file:///etc/passwd",                         # non-HTTP scheme
    "gopher://example.com/",                      # non-HTTP scheme
    "ftp://example.com/",                         # non-HTTP scheme
    "http://example.com:22/",                     # non-web port
    "http://example.com:6379/",                   # non-web port
    "http://example.com:3306/",                   # non-web port
]

ALLOWED = [
    "https://example.com/",
    "http://example.com/page?q=1",
    "https://sub.example.co.uk:8443/path",
]


@pytest.mark.parametrize("url", BLOCKED)
def test_blocked_urls_are_rejected(url):
    with pytest.raises(urlguard.BlockedURLError):
        urlguard.validate_url(url)


@pytest.mark.parametrize("url", ALLOWED)
def test_public_urls_are_allowed(url):
    scheme, host, port = urlguard.validate_url(url)
    assert scheme in ("http", "https")
    assert host


def test_url_without_host_is_rejected():
    with pytest.raises(urlguard.BlockedURLError):
        urlguard.validate_url("http:///nohost")


async def test_hostname_resolving_to_loopback_is_rejected():
    # "localhost" passes the literal-IP check but must fail on resolution.
    with pytest.raises(urlguard.BlockedURLError):
        await urlguard.check_url("http://localhost/")


def test_peer_check_rejects_a_private_connection():
    """Layer 3: the socket landed somewhere private despite a clean lookup."""

    class _Stream:
        def get_extra_info(self, name):
            return ("10.1.2.3", 80) if name == "server_addr" else None

    class _Response:
        extensions = {"network_stream": _Stream()}

    with pytest.raises(urlguard.BlockedURLError):
        urlguard.assert_peer_public(_Response())


def test_peer_check_accepts_a_public_connection():
    class _Stream:
        def get_extra_info(self, name):
            return ("93.184.216.34", 443) if name == "server_addr" else None

    class _Response:
        extensions = {"network_stream": _Stream()}

    urlguard.assert_peer_public(_Response())  # must not raise


async def test_fetch_refuses_a_blocked_target_without_connecting():
    from app.seo import fetcher

    result = await fetcher.fetch("http://169.254.169.254/latest/meta-data/")
    assert result.ok is False
    assert "not a public address" in (result.error or "")
    assert result.content == b""
