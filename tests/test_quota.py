"""Quota enforcement tests: 5 free analyses/day, then 429, plus reset logic."""
from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.exceptions import QuotaExceededError
from app.services import quota_service


@pytest.mark.asyncio
async def test_daily_limit_blocks_sixth(client, auth_headers):
    # 5 submissions succeed (202), the 6th hits the daily cap (429).
    for _ in range(5):
        r = await client.post(
            "/api/v1/analyses",
            headers=auth_headers,
            json={"url": "https://example.com"},
        )
        assert r.status_code == 202

    sixth = await client.post(
        "/api/v1/analyses",
        headers=auth_headers,
        json={"url": "https://example.com"},
    )
    assert sixth.status_code == 429
    body = sixth.json()
    assert body["error"]["code"] == "quota_exceeded"
    assert body["error"]["details"]["daily_limit"] == 5
    assert "Retry-After" in sixth.headers


@pytest.mark.asyncio
async def test_quota_status_endpoint(client, auth_headers):
    await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    r = await client.get("/api/v1/users/me/quota", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["daily_limit"] == 5
    assert body["used_today"] == 1
    assert body["remaining_today"] == 4


@pytest.mark.asyncio
async def test_daily_counter_resets_next_day(session_factory):
    """Simulate a stale day_reset_date and confirm the counter rolls over."""
    from app.crud import quota as quota_crud
    from app.crud import user as user_crud

    async with session_factory() as db:
        user = await user_crud.create(
            db, username="u1", email="u1@example.com", hashed_password="x"
        )
        quota = await quota_crud.create(db, user.id)
        quota.used_today = 5
        quota.day_reset_date = date.today() - timedelta(days=1)
        quota.month_reset_date = datetime.now(UTC)
        await db.commit()

        # consume() should reset used_today to 0 first, then increment to 1.
        refreshed = await quota_service.consume(db, user.id)
        assert refreshed.used_today == 1
        assert refreshed.day_reset_date == date.today()


@pytest.mark.asyncio
async def test_consume_raises_when_exhausted(session_factory):
    from app.crud import quota as quota_crud
    from app.crud import user as user_crud

    async with session_factory() as db:
        user = await user_crud.create(
            db, username="u2", email="u2@example.com", hashed_password="x"
        )
        quota = await quota_crud.create(db, user.id)
        quota.used_today = 5
        quota.day_reset_date = date.today()
        await db.commit()

        with pytest.raises(QuotaExceededError):
            await quota_service.consume(db, user.id)
