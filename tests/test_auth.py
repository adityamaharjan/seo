"""Auth flow tests: signup, login, me, refresh rotation, duplicate handling."""
import pytest


@pytest.mark.asyncio
async def test_signup_and_login(client):
    r = await client.post(
        "/api/v1/auth/signup",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "alice@example.com"

    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_duplicate_signup_conflicts(client):
    payload = {"username": "bob", "email": "bob@example.com", "password": "password123"}
    assert (await client.post("/api/v1/auth/signup", json=payload)).status_code == 201
    dup = await client.post("/api/v1/auth/signup", json=payload)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "conflict"


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client, auth_headers):
    r = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["username"] == "tester"


@pytest.mark.asyncio
async def test_refresh_rotates_token(client):
    await client.post(
        "/api/v1/auth/signup",
        json={"username": "carol", "email": "carol@example.com", "password": "password123"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "password123"},
    )
    old_refresh = login.json()["refresh_token"]

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200

    # The old refresh token is revoked after rotation.
    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401


@pytest.mark.asyncio
async def test_bad_login(client):
    await client.post(
        "/api/v1/auth/signup",
        json={"username": "dan", "email": "dan@example.com", "password": "password123"},
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "dan@example.com", "password": "wrongpass"},
    )
    assert r.status_code == 401
