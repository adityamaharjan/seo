"""Analysis lifecycle: submit -> job enqueued -> worker runs -> poll done."""
import httpx
import pytest
import respx

from app.services import report_service

SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Best Coffee Beans for Home Brewing in 2026</title>
  <meta name="description" content="A complete guide to choosing the best coffee beans for home brewing, covering roast levels, origins, and grind size for a great cup.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="canonical" href="https://example.com/">
</head>
<body>
  <h1>The Best Coffee Beans for Home Brewing</h1>
  <h2>Choosing a Roast</h2>
  <p>Coffee beans come in many roast levels. Light roast coffee beans keep more
  origin character, while dark roast coffee beans taste bolder. Home brewing
  works well with medium roast coffee beans for most people.</p>
  <img src="beans.webp" alt="Roasted coffee beans" width="800" height="600" loading="lazy">
  <a href="/guide">Read the full brewing guide</a>
  <a href="https://external.example.org/article">External reference</a>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_submit_enqueues_job(client, auth_headers, fake_arq):
    r = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    assert body["status_url"].endswith(f"/analyses/{body['id']}")
    assert fake_arq.jobs == [("run_analysis_task", (body["id"],))]


@pytest.mark.asyncio
@respx.mock
async def test_full_lifecycle(client, auth_headers, session_factory):
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, html=SAMPLE_HTML)
    )
    # robots.txt / sitemap / broken-link probes -> succeed generically.
    respx.route(host="example.com").mock(
        return_value=httpx.Response(200, html=SAMPLE_HTML)
    )
    respx.route().mock(return_value=httpx.Response(200, text="ok"))

    submit = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    report_id = submit.json()["id"]

    # Drive the worker task directly (the queue is faked in tests).
    async with session_factory() as db:
        await report_service.run_analysis(db, report_id)

    poll = await client.get(f"/api/v1/analyses/{report_id}", headers=auth_headers)
    assert poll.status_code == 200
    body = poll.json()
    assert body["status"] == "done"
    assert body["overall_score"] is not None
    assert body["results"]["fetched_ok"] is True
    assert any(c["id"] == "title_tag" for c in body["results"]["checks"])


@pytest.mark.asyncio
@respx.mock
async def test_target_keywords_are_scored_for_placement(
    client, auth_headers, session_factory
):
    respx.route(host="example.com").mock(
        return_value=httpx.Response(200, html=SAMPLE_HTML)
    )
    respx.route().mock(return_value=httpx.Response(200, text="ok"))

    submit = await client.post(
        "/api/v1/analyses",
        headers=auth_headers,
        json={
            "url": "https://example.com",
            "target_keywords": ["coffee beans", "  Coffee Beans ", "sock knitting"],
        },
    )
    assert submit.status_code == 202
    report_id = submit.json()["id"]

    async with session_factory() as db:
        await report_service.run_analysis(db, report_id)

    body = (
        await client.get(f"/api/v1/analyses/{report_id}", headers=auth_headers)
    ).json()
    # Case-insensitive duplicate collapsed; order preserved.
    assert body["target_keywords"] == ["coffee beans", "sock knitting"]

    # Keyword targeting is its own report, never a check inside the audit.
    report = body["results"]["keyword_report"]
    assert not any(c["id"] == "keyword_targeting" for c in body["results"]["checks"])
    results = {k["keyword"]: k for k in report["keywords"]}
    # The fixture page is about coffee beans and says nothing about knitting.
    assert results["coffee beans"]["score"] > results["sock knitting"]["score"]
    assert results["coffee beans"]["found_in"]["title"] == "exact"
    assert results["sock knitting"]["found_in"] == {}


@pytest.mark.asyncio
async def test_too_many_target_keywords_is_rejected(client, auth_headers):
    r = await client.post(
        "/api/v1/analyses",
        headers=auth_headers,
        json={
            "url": "https://example.com",
            "target_keywords": ["a1", "b2", "c3", "d4", "e5", "f6"],
        },
    )
    assert r.status_code == 422
    assert "at most 5" in r.text.lower()


@pytest.mark.asyncio
async def test_no_keyword_report_when_none_given(
    client, auth_headers, session_factory
):
    """Most analyses name no keywords, so the keyword feature produces nothing."""
    with respx.mock:
        respx.route(host="example.com").mock(
            return_value=httpx.Response(200, html=SAMPLE_HTML)
        )
        respx.route().mock(return_value=httpx.Response(200, text="ok"))
        submit = await client.post(
            "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
        )
        report_id = submit.json()["id"]
        async with session_factory() as db:
            await report_service.run_analysis(db, report_id)

    body = (
        await client.get(f"/api/v1/analyses/{report_id}", headers=auth_headers)
    ).json()
    assert body["target_keywords"] is None
    assert body["results"]["keyword_report"] is None


@pytest.mark.asyncio
@respx.mock
async def test_working_links_are_not_reported_broken(
    client, auth_headers, session_factory
):
    """Broken-link probing must actually run against a live HTTP client.

    It used to be handed back to the analyzer and awaited after the client's
    `async with` block had closed it, so every probe raised "client has been
    closed" and every sampled link came back broken — on every report.
    """
    respx.route(host="example.com").mock(
        return_value=httpx.Response(200, html=SAMPLE_HTML)
    )
    respx.route().mock(return_value=httpx.Response(200, text="ok"))

    submit = await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    report_id = submit.json()["id"]
    async with session_factory() as db:
        await report_service.run_analysis(db, report_id)

    body = (
        await client.get(f"/api/v1/analyses/{report_id}", headers=auth_headers)
    ).json()
    check = next(c for c in body["results"]["checks"] if c["id"] == "broken_links")

    # The external link resolves nowhere, so the guard reports it unreachable —
    # that part is correct. The regression is the internal link, which the mock
    # serves with a 200 and which used to come back broken regardless.
    assert check["value"] == ["https://external.example.org/article"], check["message"]
    assert check["status"] == "warning"


@pytest.mark.asyncio
async def test_get_missing_report_404(client, auth_headers):
    r = await client.get("/api/v1/analyses/99999", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_is_user_scoped(client, auth_headers):
    await client.post(
        "/api/v1/analyses", headers=auth_headers, json={"url": "https://example.com"}
    )
    r = await client.get("/api/v1/analyses", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] >= 1
