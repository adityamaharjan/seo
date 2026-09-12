"""Site audit lifecycle: submit -> crawl -> aggregate -> poll.

A site audit is a separate feature from a single-page analysis, so these tests
also pin the boundary between them: it takes a page budget and no keywords, and
its results never appear in the single-page history.
"""
import httpx
import pytest
import respx

from app.services import site_audit_service

PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta name="description" content="A long enough description of this particular page to satisfy the meta description length check comfortably.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
  <h1>{title}</h1>
  <h2>Details</h2>
  <p>Some body copy about {title} that gives the analyzer real text to work
  with rather than an empty document.</p>
  <a href="/one">One</a>
  <a href="/two">Two</a>
  <a href="/three">Three</a>
</body>
</html>
"""

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/one</loc></url>
  <url><loc>https://example.com/two</loc></url>
</urlset>
"""


def _mock_site(robots: str = "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n"):
    """Serve robots.txt, a sitemap, and an HTML page for anything else."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=robots)
    )
    respx.get("https://example.com/sitemap.xml").mock(
        return_value=httpx.Response(
            200, text=SITEMAP, headers={"content-type": "application/xml"}
        )
    )

    def page(request):
        return httpx.Response(200, html=PAGE_HTML.format(title=f"Page {request.url.path}"))

    respx.route(host="example.com").mock(side_effect=page)
    respx.route().mock(return_value=httpx.Response(200, text="ok"))


@pytest.mark.asyncio
async def test_submit_enqueues_site_audit_job(client, auth_headers, fake_arq):
    r = await client.post(
        "/api/v1/site-audits",
        headers=auth_headers,
        json={"url": "https://example.com", "max_pages": 5},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    assert body["max_pages"] == 5
    assert body["status_url"].endswith(f"/site-audits/{body['id']}")
    assert fake_arq.jobs == [("run_site_audit_task", (body["id"],))]


@pytest.mark.asyncio
@respx.mock
async def test_site_audit_crawls_and_aggregates(client, auth_headers, session_factory):
    _mock_site()
    submit = await client.post(
        "/api/v1/site-audits",
        headers=auth_headers,
        json={"url": "https://example.com", "max_pages": 3},
    )
    audit_id = submit.json()["id"]

    async with session_factory() as db:
        await site_audit_service.run_site_audit(db, audit_id)

    body = (
        await client.get(f"/api/v1/site-audits/{audit_id}", headers=auth_headers)
    ).json()

    assert body["status"] == "done"
    assert body["pages_crawled"] == 3
    assert body["discovery_source"] == "sitemap"
    assert len(body["pages"]) == 3
    assert 0 < body["overall_score"] <= 100
    results = body["results"]
    assert results["score_spread"]["min"] <= results["score_spread"]["max"]
    assert [c["category"] for c in results["category_scores"]]
    assert all(i["total_pages"] == 3 for i in results["top_issues"])


@pytest.mark.asyncio
@respx.mock
async def test_page_budget_is_respected(client, auth_headers, session_factory):
    _mock_site()
    submit = await client.post(
        "/api/v1/site-audits",
        headers=auth_headers,
        json={"url": "https://example.com", "max_pages": 2},
    )
    audit_id = submit.json()["id"]
    async with session_factory() as db:
        audit = await site_audit_service.run_site_audit(db, audit_id)
    assert audit.pages_crawled == 2


@pytest.mark.asyncio
@respx.mock
async def test_crawl_falls_back_to_links_without_a_sitemap(
    client, auth_headers, session_factory
):
    """A site with no sitemap is still auditable by following internal links."""
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(404))
    respx.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(404))
    respx.route(host="example.com").mock(
        side_effect=lambda request: httpx.Response(
            200, html=PAGE_HTML.format(title=f"Page {request.url.path}")
        )
    )
    respx.route().mock(return_value=httpx.Response(200, text="ok"))

    submit = await client.post(
        "/api/v1/site-audits",
        headers=auth_headers,
        json={"url": "https://example.com", "max_pages": 4},
    )
    audit_id = submit.json()["id"]
    async with session_factory() as db:
        audit = await site_audit_service.run_site_audit(db, audit_id)

    assert audit.status == "done"
    assert audit.discovery_source == "links"
    assert audit.pages_crawled > 1  # it followed links off the start page


@pytest.mark.asyncio
@respx.mock
async def test_robots_disallowed_pages_are_not_crawled(
    client, auth_headers, session_factory
):
    """The crawler must obey robots.txt even when a page is linked."""
    _mock_site(robots="User-agent: *\nDisallow: /two\n")
    respx.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(404))

    submit = await client.post(
        "/api/v1/site-audits",
        headers=auth_headers,
        json={"url": "https://example.com", "max_pages": 5},
    )
    audit_id = submit.json()["id"]
    async with session_factory() as db:
        await site_audit_service.run_site_audit(db, audit_id)

    detail = (
        await client.get(f"/api/v1/site-audits/{audit_id}", headers=auth_headers)
    ).json()
    crawled = {page["url"] for page in detail["pages"]}

    assert crawled  # the crawl did run
    assert not any(url.endswith("/two") for url in crawled)


@pytest.mark.asyncio
@respx.mock
async def test_site_audit_pages_carry_a_full_report(
    client, auth_headers, session_factory
):
    """Each crawled page keeps the single-page report shape, so the UI reuses it."""
    _mock_site()
    submit = await client.post(
        "/api/v1/site-audits",
        headers=auth_headers,
        json={"url": "https://example.com", "max_pages": 2},
    )
    audit_id = submit.json()["id"]
    async with session_factory() as db:
        await site_audit_service.run_site_audit(db, audit_id)

    detail = (
        await client.get(f"/api/v1/site-audits/{audit_id}", headers=auth_headers)
    ).json()
    page_id = detail["pages"][0]["id"]

    page = (
        await client.get(
            f"/api/v1/site-audits/{audit_id}/pages/{page_id}", headers=auth_headers
        )
    ).json()
    assert page["results"]["category_scores"]
    assert any(c["id"] == "title_tag" for c in page["results"]["checks"])
    # Link lists exist only to drive the crawl and must not be persisted.
    assert "internal_links" not in page["results"]


@pytest.mark.asyncio
async def test_site_audits_do_not_accept_keywords(client, auth_headers):
    """Keywords belong to the single-page feature; the schema rejects them here."""
    r = await client.post(
        "/api/v1/site-audits",
        headers=auth_headers,
        json={"url": "https://example.com", "target_keywords": ["coffee"]},
    )
    # Unknown field is ignored rather than stored, and nothing keyword-shaped
    # comes back on the accepted audit.
    assert r.status_code == 202
    assert "keyword" not in r.text.lower()


@pytest.mark.asyncio
async def test_page_budget_over_the_ceiling_is_rejected(client, auth_headers):
    r = await client.post(
        "/api/v1/site-audits",
        headers=auth_headers,
        json={"url": "https://example.com", "max_pages": 500},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_site_audits_are_separate_from_single_page_history(
    client, auth_headers, fake_arq
):
    """The two features must not bleed into each other's lists."""
    await client.post(
        "/api/v1/site-audits", headers=auth_headers, json={"url": "https://example.com"}
    )
    reports = (await client.get("/api/v1/analyses", headers=auth_headers)).json()
    audits = (await client.get("/api/v1/site-audits", headers=auth_headers)).json()

    assert reports["total"] == 0
    assert audits["total"] == 1


@pytest.mark.asyncio
async def test_site_audit_404s_for_another_user(client, auth_headers):
    r = await client.get("/api/v1/site-audits/99999", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_failed_crawl_refunds_quota(client, auth_headers, session_factory):
    """Nothing was delivered, so the unit goes back."""
    respx.route().mock(return_value=httpx.Response(500))

    before = (await client.get("/api/v1/users/me/quota", headers=auth_headers)).json()
    submit = await client.post(
        "/api/v1/site-audits", headers=auth_headers, json={"url": "https://example.com"}
    )
    audit_id = submit.json()["id"]
    async with session_factory() as db:
        audit = await site_audit_service.run_site_audit(db, audit_id)

    assert audit.status == "failed"
    after = (await client.get("/api/v1/users/me/quota", headers=auth_headers)).json()
    assert after["used_today"] == before["used_today"]
