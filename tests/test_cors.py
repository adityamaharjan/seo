"""CORS behaviour for a frontend hosted on a different origin.

These matter when the app is deployed to Vercel or Cloudflare Pages rather than
served from the same host as the API.
"""
import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import Settings

FRONTEND = "https://seo-frontend.vercel.app"


@pytest.mark.asyncio
async def test_retry_after_is_readable_cross_origin(client, auth_headers):
    """The frontend shows "try again in N minutes", which needs this header.

    Retry-After is not CORS-safelisted, so without expose_headers the browser
    hands the app a 429 with no reset time.
    """
    for _ in range(5):
        await client.post(
            "/api/v1/analyses",
            headers={**auth_headers, "Origin": FRONTEND},
            json={"url": "https://example.com"},
        )

    blocked = await client.post(
        "/api/v1/analyses",
        headers={**auth_headers, "Origin": FRONTEND},
        json={"url": "https://example.com"},
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers

    exposed = blocked.headers.get("access-control-expose-headers", "")
    assert "Retry-After" in exposed
    assert "X-Request-ID" in exposed


@pytest.mark.asyncio
async def test_preflight_is_answered(client):
    response = await client.request(
        "OPTIONS",
        "/api/v1/analyses",
        headers={
            "Origin": FRONTEND,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] in (FRONTEND, "*")
    assert "POST" in response.headers.get("access-control-allow-methods", "")


def test_origin_regex_must_be_anchored_in_production():
    """An unanchored pattern matches any origin that merely contains it."""
    base = {
        "ENVIRONMENT": "production",
        "JWT_SECRET": "x" * 48,
        "CORS_ORIGINS": ["https://app.example.com"],
    }
    with pytest.raises(ValidationError) as excinfo:
        Settings(**base, CORS_ORIGIN_REGEX="https://.*\\.vercel\\.app")
    assert "anchored" in str(excinfo.value)


def test_catch_all_origin_regex_is_refused_in_production():
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="x" * 48,
            CORS_ORIGINS=["https://app.example.com"],
            CORS_ORIGIN_REGEX="^.*$",
        )
    assert "every origin" in str(excinfo.value)


def test_anchored_preview_regex_is_accepted():
    settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET="x" * 48,
        CORS_ORIGINS=["https://seo-frontend.vercel.app"],
        CORS_ORIGIN_REGEX=r"^https://seo-frontend-[a-z0-9-]+\.vercel\.app$",
        API_KEY_ENCRYPTION_KEY=Fernet.generate_key().decode(),
    )
    assert settings.CORS_ORIGIN_REGEX is not None


def test_invalid_regex_is_rejected():
    with pytest.raises(ValidationError):
        Settings(CORS_ORIGIN_REGEX="^https://[unclosed$")


def test_comma_separated_origins_parse_from_the_environment(monkeypatch):
    """The documented form must survive pydantic-settings' JSON decoding.

    Without NoDecode on the field, `CORS_ORIGINS=https://a.example.com` raises
    a JSON decode error and the process refuses to start.
    """
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example.com,https://b.example.com")
    monkeypatch.setenv("CORS_EXPOSE_HEADERS", "Retry-After,X-Request-ID")
    settings = Settings()
    assert settings.CORS_ORIGINS == ["https://a.example.com", "https://b.example.com"]
    assert settings.CORS_EXPOSE_HEADERS == ["Retry-After", "X-Request-ID"]


def test_wildcard_origin_still_parses_from_the_environment(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    assert Settings().CORS_ORIGINS == ["*"]
