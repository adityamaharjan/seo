"""Choosing whether a run uses PageSpeed Insights.

Three ways to express the choice, all tested here: explicitly on (fails loudly
with no key), explicitly off (never runs), and omitted (follows whatever the
account has). The resolution itself lives in
:func:`app.services.api_key_service.resolve_psi_key`.
"""
import httpx
import pytest
import respx
from cryptography.fernet import Fernet

from app.core.config import settings
from app.models.site_audit import PSI_SAMPLE_SIZE, PsiScope, SiteAudit
from app.seo.psi import ENDPOINT
from app.services import api_key_service

REAL_KEY = "AIzaSyTestKeyLooksLikeThis1234567890abc"


@pytest.fixture
def encryption_configured(monkeypatch):
    monkeypatch.setattr(
        settings, "API_KEY_ENCRYPTION_KEY", Fernet.generate_key().decode()
    )


@pytest.fixture
def no_server_key(monkeypatch):
    """Strip the development fallback so BYOK behaviour is what is tested."""
    monkeypatch.setattr(settings, "GOOGLE_PAGE_SPEED_INSIGHTS_API_KEY", "")


@pytest.fixture
def psi_accepts():
    with respx.mock:
        respx.get(ENDPOINT).mock(return_value=httpx.Response(200, json={}))
        yield


async def save_key(client, auth_headers):
    r = await client.put(
        "/api/v1/users/me/api-keys/google_psi",
        headers=auth_headers,
        json={"key": REAL_KEY},
    )
    assert r.status_code == 200


# --- the explicit ask ------------------------------------------------------


@pytest.mark.asyncio
async def test_requesting_psi_without_a_key_is_rejected_before_quota(
    client, auth_headers, fake_arq, no_server_key
):
    """Rejected at submit time, so the user finds out while looking at the form
    rather than getting a report that silently lacks the data they asked for.
    Quota is charged by a dependency, so the 400 also leaves it unspent."""
    quota_before = (await client.get("/api/v1/users/me/quota", headers=auth_headers)).json()

    r = await client.post(
        "/api/v1/analyses",
        headers=auth_headers,
        json={"url": "https://example.com", "use_psi": True},
    )
    assert r.status_code == 400
    assert "no PageSpeed Insights key is saved" in r.json()["error"]["message"]

    quota_after = (await client.get("/api/v1/users/me/quota", headers=auth_headers)).json()
    assert quota_after["used_today"] == quota_before["used_today"]


@pytest.mark.asyncio
async def test_omitting_the_choice_never_fails(
    client, auth_headers, fake_arq, no_server_key
):
    """A caller that has never heard of PageSpeed keeps working unchanged."""
    r = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_saved_key_turns_psi_on_by_default(
    client, auth_headers, fake_arq, encryption_configured, psi_accepts, no_server_key
):
    await save_key(client, auth_headers)
    r = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    assert r.status_code == 202
    detail = await client.get(f"/api/v1/analyses/{r.json()['id']}", headers=auth_headers)
    assert detail.json()["used_psi"] is True


@pytest.mark.asyncio
async def test_opting_out_skips_psi_even_with_a_key_saved(
    client, auth_headers, fake_arq, encryption_configured, psi_accepts, no_server_key
):
    """Turning it off must not require deleting the stored key."""
    await save_key(client, auth_headers)
    r = await client.post(
        "/api/v1/analyses",
        headers=auth_headers,
        json={"url": "https://example.com", "use_psi": False},
    )
    assert r.status_code == 202
    detail = await client.get(f"/api/v1/analyses/{r.json()['id']}", headers=auth_headers)
    assert detail.json()["used_psi"] is False


# --- key resolution --------------------------------------------------------


@pytest.mark.asyncio
async def test_server_key_is_a_development_fallback_only(
    session_factory, monkeypatch, client, auth_headers
):
    """A server-wide key would put every user on one quota and one bill, so it
    must never apply in production."""
    monkeypatch.setattr(settings, "GOOGLE_PAGE_SPEED_INSIGHTS_API_KEY", "dev-key")
    async with session_factory() as db:
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        assert await api_key_service.resolve_psi_key(db, 1, requested=None) == "dev-key"

        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        assert await api_key_service.resolve_psi_key(db, 1, requested=None) is None


@pytest.mark.asyncio
async def test_explicit_opt_out_short_circuits_any_key(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_PAGE_SPEED_INSIGHTS_API_KEY", "dev-key")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    async with session_factory() as db:
        assert await api_key_service.resolve_psi_key(db, 1, requested=False) is None


@pytest.mark.asyncio
async def test_failure_is_recorded_against_the_stored_key(
    client, auth_headers, session_factory, encryption_configured, psi_accepts
):
    """``last_error`` in the settings screen is what makes a key that has
    started failing on quota visible, instead of reports quietly losing data."""
    await save_key(client, auth_headers)
    from app.crud import api_key as api_key_crud

    async with session_factory() as db:
        row = (await api_key_crud.list_for_user(db, 1))[0]
        user_id = row.user_id
        await api_key_service.record_psi_outcome(db, user_id, error="Quota exceeded")
        await db.commit()

    listing = await client.get("/api/v1/users/me/api-keys", headers=auth_headers)
    google = {p["provider"]: p for p in listing.json()["providers"]}["google_psi"]
    assert google["last_error"] == "Quota exceeded"
    assert google["last_used_at"] is not None


@pytest.mark.asyncio
async def test_success_clears_a_previous_failure(
    client, auth_headers, session_factory, encryption_configured, psi_accepts
):
    await save_key(client, auth_headers)
    from app.crud import api_key as api_key_crud

    async with session_factory() as db:
        user_id = (await api_key_crud.list_for_user(db, 1))[0].user_id
        await api_key_service.record_psi_outcome(db, user_id, error="Quota exceeded")
        await api_key_service.record_psi_outcome(db, user_id, error=None)
        await db.commit()

    listing = await client.get("/api/v1/users/me/api-keys", headers=auth_headers)
    google = {p["provider"]: p for p in listing.json()["providers"]}["google_psi"]
    assert google["last_error"] is None


@pytest.mark.asyncio
async def test_recording_an_outcome_with_no_stored_key_is_harmless(session_factory):
    """A run on the development fallback has no row to record against."""
    async with session_factory() as db:
        await api_key_service.record_psi_outcome(db, 999, error="boom")


# --- site audit scope ------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_scope_is_persisted(
    client, auth_headers, session_factory, encryption_configured, psi_accepts,
    no_server_key,
):
    await save_key(client, auth_headers)
    r = await client.post(
        "/api/v1/site-audits",
        headers=auth_headers,
        json={"url": "https://example.com", "max_pages": 5, "psi_scope": "homepage"},
    )
    assert r.status_code == 202
    assert r.json()["status"] == "pending"

    async with session_factory() as db:
        audit = await db.get(SiteAudit, r.json()["id"])
        assert audit.used_psi is True
        assert audit.psi_scope == "homepage"


@pytest.mark.asyncio
async def test_audit_without_a_key_records_scope_off(
    client, auth_headers, fake_arq, no_server_key, session_factory
):
    r = await client.post(
        "/api/v1/site-audits",
        headers=auth_headers,
        json={"url": "https://example.com", "max_pages": 5},
    )
    assert r.status_code == 202
    async with session_factory() as db:
        audit = await db.get(SiteAudit, r.json()["id"])
        assert audit.used_psi is False
        assert audit.psi_scope == PsiScope.off.value


@pytest.mark.asyncio
async def test_an_unknown_scope_is_rejected(client, auth_headers, fake_arq):
    r = await client.post(
        "/api/v1/site-audits",
        headers=auth_headers,
        json={"url": "https://example.com", "psi_scope": "everything"},
    )
    assert r.status_code == 422


def test_psi_budget_per_scope():
    """The budget bounds how much of a crawl pays the PSI time cost."""
    from app.services.site_audit_service import _psi_budget

    def audit(scope, max_pages=50):
        return SiteAudit(start_url="https://example.com", max_pages=max_pages,
                         psi_scope=scope)

    assert _psi_budget(audit(PsiScope.off)) == 0
    assert _psi_budget(audit(PsiScope.homepage)) == 1
    assert _psi_budget(audit(PsiScope.sample)) == PSI_SAMPLE_SIZE
    assert _psi_budget(audit(PsiScope.all)) == 50
    # A crawl smaller than the sample size cannot spend more than it crawls.
    assert _psi_budget(audit(PsiScope.sample, max_pages=2)) == 2
    # An audit predating the feature has no scope stored at all.
    assert _psi_budget(audit(None)) == 0
