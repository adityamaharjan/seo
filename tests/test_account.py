"""Self-service account management: profile edits and password changes."""
import pytest


@pytest.mark.asyncio
async def test_update_username_and_email(client, auth_headers):
    r = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"username": "renamed", "email": "renamed@example.com"},
    )
    assert r.status_code == 200
    assert r.json()["username"] == "renamed"
    assert r.json()["email"] == "renamed@example.com"

    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.json()["username"] == "renamed"


@pytest.mark.asyncio
async def test_partial_update_leaves_the_other_field_alone(client, auth_headers):
    r = await client.patch(
        "/api/v1/users/me", headers=auth_headers, json={"username": "solo"}
    )
    assert r.status_code == 200
    assert r.json()["username"] == "solo"
    assert r.json()["email"] == "tester@example.com"


@pytest.mark.asyncio
async def test_empty_update_is_rejected(client, auth_headers):
    r = await client.patch("/api/v1/users/me", headers=auth_headers, json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_taken_username_is_a_conflict(client, auth_headers, make_user):
    await make_user("taken", "taken@example.com")
    r = await client.patch(
        "/api/v1/users/me", headers=auth_headers, json={"username": "taken"}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


@pytest.mark.asyncio
async def test_keeping_your_own_username_is_not_a_conflict(client, auth_headers):
    r = await client.patch(
        "/api/v1/users/me", headers=auth_headers, json={"username": "tester"}
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_password_change_requires_the_current_password(client, auth_headers):
    r = await client.post(
        "/api/v1/users/me/password",
        headers=auth_headers,
        json={"current_password": "wrongwrong", "new_password": "brandnewpass1"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_new_password_must_differ(client, auth_headers):
    r = await client.post(
        "/api/v1/users/me/password",
        headers=auth_headers,
        json={"current_password": "supersecret123", "new_password": "supersecret123"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_password_change_signs_other_sessions_out(client, auth_headers):
    """A password change is usually a response to exposure, so live refresh
    tokens must stop working rather than outliving the old password."""
    second = await client.post(
        "/api/v1/auth/login",
        json={"email": "tester@example.com", "password": "supersecret123"},
    )
    stale_refresh = second.json()["refresh_token"]

    changed = await client.post(
        "/api/v1/users/me/password",
        headers=auth_headers,
        json={"current_password": "supersecret123", "new_password": "brandnewpass1"},
    )
    assert changed.status_code == 200
    assert changed.json()["revoked"] >= 1

    reused = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": stale_refresh}
    )
    assert reused.status_code == 401

    old = await client.post(
        "/api/v1/auth/login",
        json={"email": "tester@example.com", "password": "supersecret123"},
    )
    assert old.status_code == 401

    new = await client.post(
        "/api/v1/auth/login",
        json={"email": "tester@example.com", "password": "brandnewpass1"},
    )
    assert new.status_code == 200


@pytest.mark.asyncio
async def test_account_endpoints_need_authentication(client):
    assert (await client.patch("/api/v1/users/me", json={"username": "x"})).status_code == 401
    assert (
        await client.post(
            "/api/v1/users/me/password",
            json={"current_password": "a", "new_password": "bbbbbbbb"},
        )
    ).status_code == 401
