"""Administrator user management, including the lockout guard rails."""
import pytest

ADMIN_USERS = "/api/v1/admin/users"


@pytest.mark.asyncio
async def test_normal_users_are_refused(client, auth_headers):
    r = await client.get(ADMIN_USERS, headers=auth_headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_anonymous_callers_are_refused(client):
    assert (await client.get(ADMIN_USERS)).status_code == 401


@pytest.mark.asyncio
async def test_list_returns_users_with_quota_and_report_counts(
    client, admin_headers, auth_headers
):
    await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )

    r = await client.get(ADMIN_USERS, headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2

    tester = next(u for u in body["items"] if u["email"] == "tester@example.com")
    assert tester["quota"]["daily_limit"] == 5
    assert tester["report_count"] == 1
    assert "hashed_password" not in tester


@pytest.mark.asyncio
async def test_search_and_role_filters(client, admin_headers, auth_headers):
    by_email = await client.get(
        ADMIN_USERS, headers=admin_headers, params={"search": "tester@"}
    )
    assert [u["email"] for u in by_email.json()["items"]] == ["tester@example.com"]

    admins = await client.get(ADMIN_USERS, headers=admin_headers, params={"role": "admin"})
    assert all(u["role"] == "admin" for u in admins.json()["items"])
    assert admins.json()["total"] == 1


@pytest.mark.asyncio
async def test_get_one_user(client, admin_headers, auth_headers):
    listing = await client.get(ADMIN_USERS, headers=admin_headers)
    target = next(u for u in listing.json()["items"] if u["email"] == "tester@example.com")

    r = await client.get(f"{ADMIN_USERS}/{target['id']}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["username"] == "tester"

    assert (await client.get(f"{ADMIN_USERS}/99999", headers=admin_headers)).status_code == 404


@pytest.mark.asyncio
async def test_promote_and_demote(client, admin_headers, auth_headers):
    listing = await client.get(ADMIN_USERS, headers=admin_headers)
    target = next(u for u in listing.json()["items"] if u["email"] == "tester@example.com")

    promoted = await client.patch(
        f"{ADMIN_USERS}/{target['id']}", headers=admin_headers, json={"role": "admin"}
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_disabling_a_user_blocks_them_immediately(
    client, admin_headers, auth_headers
):
    listing = await client.get(ADMIN_USERS, headers=admin_headers)
    target = next(u for u in listing.json()["items"] if u["email"] == "tester@example.com")

    disabled = await client.patch(
        f"{ADMIN_USERS}/{target['id']}", headers=admin_headers, json={"is_active": False}
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    # Their existing access token must stop working, not linger until expiry.
    blocked = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert blocked.status_code == 401

    denied = await client.post(
        "/api/v1/auth/login",
        json={"email": "tester@example.com", "password": "supersecret123"},
    )
    assert denied.status_code == 401


@pytest.mark.asyncio
async def test_admin_cannot_demote_or_disable_themselves(client, admin_headers):
    listing = await client.get(ADMIN_USERS, headers=admin_headers)
    me = next(u for u in listing.json()["items"] if u["email"] == "boss@example.com")

    demote = await client.patch(
        f"{ADMIN_USERS}/{me['id']}", headers=admin_headers, json={"role": "user"}
    )
    assert demote.status_code == 403

    disable = await client.patch(
        f"{ADMIN_USERS}/{me['id']}", headers=admin_headers, json={"is_active": False}
    )
    assert disable.status_code == 403


@pytest.mark.asyncio
async def test_the_last_admin_cannot_be_removed(client, admin_headers, make_user, session_factory):
    """Two admins, so the guard is exercised on someone other than the actor."""
    from sqlalchemy import select

    from app.models.user import User, UserRole

    await make_user("second", "second@example.com")
    async with session_factory() as db:
        res = await db.execute(select(User).where(User.email == "second@example.com"))
        second = res.scalar_one()
        second.role = UserRole.admin
        await db.commit()
        second_id = second.id

    # Demoting one of two admins is allowed.
    first = await client.patch(
        f"{ADMIN_USERS}/{second_id}", headers=admin_headers, json={"role": "user"}
    )
    assert first.status_code == 200

    # Now only the actor is left, and they cannot demote themselves either.
    listing = await client.get(ADMIN_USERS, headers=admin_headers)
    me = next(u for u in listing.json()["items"] if u["email"] == "boss@example.com")
    assert (
        await client.patch(
            f"{ADMIN_USERS}/{me['id']}", headers=admin_headers, json={"role": "user"}
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_quota_override_changes_what_the_user_can_do(
    client, admin_headers, auth_headers
):
    listing = await client.get(ADMIN_USERS, headers=admin_headers)
    target = next(u for u in listing.json()["items"] if u["email"] == "tester@example.com")

    r = await client.patch(
        f"{ADMIN_USERS}/{target['id']}/quota",
        headers=admin_headers,
        json={"daily_limit": 1, "monthly_limit": 10},
    )
    assert r.status_code == 200
    assert r.json()["quota"]["daily_limit"] == 1

    seen = await client.get("/api/v1/users/me/quota", headers=auth_headers)
    assert seen.json()["daily_limit"] == 1
    assert seen.json()["remaining_today"] == 1

    first = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    assert first.status_code == 202
    second = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    assert second.status_code == 429


@pytest.mark.asyncio
async def test_revoke_sessions(client, admin_headers, auth_headers):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "tester@example.com", "password": "supersecret123"},
    )
    refresh_token = login.json()["refresh_token"]

    listing = await client.get(ADMIN_USERS, headers=admin_headers)
    target = next(u for u in listing.json()["items"] if u["email"] == "tester@example.com")

    r = await client.post(
        f"{ADMIN_USERS}/{target['id']}/revoke-sessions", headers=admin_headers
    )
    assert r.status_code == 200
    assert r.json()["revoked"] >= 1

    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reused.status_code == 401


@pytest.mark.asyncio
async def test_delete_user_removes_their_reports(
    client, admin_headers, auth_headers, session_factory
):
    submitted = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    report_id = submitted.json()["id"]

    listing = await client.get(ADMIN_USERS, headers=admin_headers)
    target = next(u for u in listing.json()["items"] if u["email"] == "tester@example.com")

    r = await client.delete(f"{ADMIN_USERS}/{target['id']}", headers=admin_headers)
    assert r.status_code == 204

    assert (await client.get(f"{ADMIN_USERS}/{target['id']}", headers=admin_headers)).status_code == 404

    from app.crud import report as report_crud

    async with session_factory() as db:
        assert await report_crud.get(db, report_id) is None


@pytest.mark.asyncio
async def test_admin_cannot_delete_themselves(client, admin_headers):
    listing = await client.get(ADMIN_USERS, headers=admin_headers)
    me = next(u for u in listing.json()["items"] if u["email"] == "boss@example.com")
    r = await client.delete(f"{ADMIN_USERS}/{me['id']}", headers=admin_headers)
    assert r.status_code == 403
