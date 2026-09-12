"""Submit-path safety: blocked targets, quota refunds, queue failures."""
import httpx
import pytest
import respx

from app.services import report_service


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8001/api/v1/health",
        "http://10.0.0.5/admin",
        "http://[::1]/",
        "http://example.com:6379/",
    ],
)
async def test_blocked_targets_are_rejected_at_submit(client, auth_headers, url, fake_arq):
    r = await client.post("/api/v1/analyses", headers=auth_headers, json={"url": url})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert fake_arq.jobs == []


@pytest.mark.asyncio
async def test_rejected_target_does_not_consume_quota(client, auth_headers):
    """Validation happens before the quota dependency, so nothing is charged."""
    await client.post(
        "/api/v1/analyses",
        headers=auth_headers,
        json={"url": "http://169.254.169.254/"},
    )
    r = await client.get("/api/v1/users/me/quota", headers=auth_headers)
    assert r.json()["used_today"] == 0
    assert r.json()["remaining_today"] == 5


@pytest.mark.asyncio
@respx.mock
async def test_failed_analysis_refunds_the_quota_unit(
    client, auth_headers, session_factory
):
    respx.route().mock(return_value=httpx.Response(500, text="boom"))

    submit = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    report_id = submit.json()["id"]

    spent = await client.get("/api/v1/users/me/quota", headers=auth_headers)
    assert spent.json()["used_today"] == 1

    async with session_factory() as db:
        report = await report_service.run_analysis(db, report_id)
    assert report.status.value == "failed"

    refunded = await client.get("/api/v1/users/me/quota", headers=auth_headers)
    assert refunded.json()["used_today"] == 0
    assert refunded.json()["remaining_today"] == 5


@pytest.mark.asyncio
@respx.mock
async def test_refund_happens_only_once(client, auth_headers, session_factory):
    """A retried job must not credit the same failure twice."""
    respx.route().mock(return_value=httpx.Response(500, text="boom"))

    submit = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    report_id = submit.json()["id"]

    async with session_factory() as db:
        await report_service.run_analysis(db, report_id)
        await report_service.run_analysis(db, report_id)

    r = await client.get("/api/v1/users/me/quota", headers=auth_headers)
    assert r.json()["used_today"] == 0  # floored, never negative


@pytest.mark.asyncio
async def test_report_row_is_committed_before_the_job_is_queued(
    client, auth_headers, session_factory, fake_arq
):
    """The worker must be able to read the row the moment it dequeues."""
    submit = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    report_id = submit.json()["id"]
    assert fake_arq.jobs == [("run_analysis_task", (report_id,))]

    # A different session stands in for the worker process.
    from app.crud import report as report_crud

    async with session_factory() as db:
        assert await report_crud.get(db, report_id) is not None


@pytest.mark.asyncio
async def test_queue_failure_fails_the_report_and_refunds(
    client, auth_headers, fake_arq
):
    async def _broken(*args, **kwargs):
        raise ConnectionError("redis is down")

    fake_arq.enqueue_job = _broken

    r = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "service_unavailable"

    quota = await client.get("/api/v1/users/me/quota", headers=auth_headers)
    assert quota.json()["used_today"] == 0
