"""User-supplied provider API keys: storage, encryption, validation, removal."""
import httpx
import pytest
import respx
from cryptography.fernet import Fernet
from pydantic import ValidationError
from sqlalchemy import select

from app.core import crypto
from app.core.config import Settings, settings
from app.crud import api_key as api_key_crud
from app.models.api_key import ApiKeyProvider, UserApiKey
from app.models.user import User
from app.seo.psi import ENDPOINT
from app.services import api_key_service

REAL_KEY = "AIzaSyTestKeyLooksLikeThis1234567890abc"


@pytest.fixture
def encryption_configured(monkeypatch):
    """Give the server a real Fernet key so storage is exercised end to end."""
    monkeypatch.setattr(
        settings, "API_KEY_ENCRYPTION_KEY", Fernet.generate_key().decode()
    )
    return settings.API_KEY_ENCRYPTION_KEY


@pytest.fixture
def psi_accepts():
    with respx.mock:
        respx.get(ENDPOINT).mock(return_value=httpx.Response(200, json={}))
        yield


@pytest.fixture
def psi_rejects():
    with respx.mock:
        respx.get(ENDPOINT).mock(
            return_value=httpx.Response(
                400,
                json={
                    "error": {
                        "code": 400,
                        "message": "API key not valid. Please pass a valid API key.",
                    }
                },
            )
        )
        yield


@pytest.mark.asyncio
async def test_providers_start_unconfigured(client, auth_headers):
    r = await client.get("/api/v1/users/me/api-keys", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    providers = {p["provider"]: p for p in body["providers"]}
    assert providers["google_psi"]["configured"] is False
    assert providers["google_psi"]["key_hint"] is None


@pytest.mark.asyncio
async def test_save_key_encrypts_at_rest(
    client, auth_headers, session_factory, encryption_configured, psi_accepts
):
    r = await client.put(
        "/api/v1/users/me/api-keys/google_psi",
        headers=auth_headers,
        json={"key": REAL_KEY},
    )
    assert r.status_code == 200
    stored = {p["provider"]: p for p in r.json()["providers"]}["google_psi"]
    assert stored["configured"] is True
    assert stored["key_hint"] == REAL_KEY[-4:]

    async with session_factory() as db:
        row = (await db.execute(select(UserApiKey))).scalar_one()
        assert REAL_KEY not in row.encrypted_key  # actually encrypted
        assert crypto.decrypt(row.encrypted_key) == REAL_KEY


@pytest.mark.asyncio
async def test_key_is_never_echoed_back(
    client, auth_headers, encryption_configured, psi_accepts
):
    save = await client.put(
        "/api/v1/users/me/api-keys/google_psi",
        headers=auth_headers,
        json={"key": REAL_KEY},
    )
    listing = await client.get("/api/v1/users/me/api-keys", headers=auth_headers)
    assert REAL_KEY not in save.text
    assert REAL_KEY not in listing.text


@pytest.mark.asyncio
async def test_provider_rejection_is_reported_as_400(
    client, auth_headers, encryption_configured, psi_rejects
):
    r = await client.put(
        "/api/v1/users/me/api-keys/google_psi",
        headers=auth_headers,
        json={"key": "wrong"},
    )
    assert r.status_code == 400
    assert "rejected this key" in r.json()["error"]["message"]


@pytest.mark.asyncio
async def test_storage_refused_without_encryption_key(
    client, auth_headers, monkeypatch, psi_accepts
):
    """No encryption key must mean no storage, never plaintext storage."""
    monkeypatch.setattr(settings, "API_KEY_ENCRYPTION_KEY", "")
    r = await client.put(
        "/api/v1/users/me/api-keys/google_psi",
        headers=auth_headers,
        json={"key": REAL_KEY},
    )
    assert r.status_code == 503
    assert "API_KEY_ENCRYPTION_KEY" in r.json()["error"]["message"]


@pytest.mark.asyncio
async def test_delete_key(client, auth_headers, encryption_configured, psi_accepts):
    await client.put(
        "/api/v1/users/me/api-keys/google_psi",
        headers=auth_headers,
        json={"key": REAL_KEY},
    )
    deleted = await client.delete(
        "/api/v1/users/me/api-keys/google_psi", headers=auth_headers
    )
    assert deleted.status_code == 204

    listing = await client.get("/api/v1/users/me/api-keys", headers=auth_headers)
    providers = {p["provider"]: p for p in listing.json()["providers"]}
    assert providers["google_psi"]["configured"] is False


@pytest.mark.asyncio
async def test_delete_missing_key_is_404(client, auth_headers):
    r = await client.delete(
        "/api/v1/users/me/api-keys/google_psi", headers=auth_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_api_keys_require_auth(client):
    assert (await client.get("/api/v1/users/me/api-keys")).status_code == 401


@pytest.mark.asyncio
async def test_rotating_the_server_key_reads_as_no_key(
    client, auth_headers, session_factory, encryption_configured, monkeypatch
):
    """A rotated API_KEY_ENCRYPTION_KEY must degrade, not raise."""
    async with session_factory() as db:
        user = (
            await db.execute(select(User).where(User.email == "tester@example.com"))
        ).scalar_one()
        await api_key_crud.upsert(
            db,
            user_id=user.id,
            provider=ApiKeyProvider.google_psi,
            encrypted_key=crypto.encrypt(REAL_KEY),
            key_hint=REAL_KEY[-4:],
        )
        await db.commit()

        assert (
            await api_key_service.get_key(
                db, user_id=user.id, provider=ApiKeyProvider.google_psi
            )
            == REAL_KEY
        )

        monkeypatch.setattr(
            settings, "API_KEY_ENCRYPTION_KEY", Fernet.generate_key().decode()
        )
        assert (
            await api_key_service.get_key(
                db, user_id=user.id, provider=ApiKeyProvider.google_psi
            )
            is None
        )


def test_malformed_encryption_key_fails_at_boot():
    with pytest.raises(ValidationError, match="valid Fernet key"):
        Settings(API_KEY_ENCRYPTION_KEY="not-a-fernet-key")


def test_empty_encryption_key_is_allowed():
    assert Settings(API_KEY_ENCRYPTION_KEY="   ").API_KEY_ENCRYPTION_KEY == ""
