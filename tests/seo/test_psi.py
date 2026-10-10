"""PageSpeed Insights parsing, scoring and the no-key degradation path.

Everything here runs against captured response shapes rather than the live
API: a real PSI call is 10-30 seconds and consumes quota, which makes it
unusable in a test suite.
"""
import asyncio

import httpx
import pytest
import respx

from app.seo import analyzer, psi
from app.seo.checks import ALL_CHECKS
from app.seo.checks import performance as perf_checks
from app.seo.constants import LCP_GOOD_MS
from tests.seo.test_checks import build_context


def lighthouse_payload(
    *,
    performance=0.95,
    lcp_ms=1800.0,
    cls=0.02,
    tbt_ms=90.0,
    field=True,
    audits=None,
):
    """A PSI response trimmed to the fields :func:`psi.parse` reads."""
    metrics = {
        "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 2100, "category": "FAST"},
        "INTERACTION_TO_NEXT_PAINT": {"percentile": 150, "category": "FAST"},
        # CrUX scales CLS by 100, so 8 here means a real value of 0.08.
        "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 8, "category": "AVERAGE"},
    }
    return {
        "id": "https://example.com/",
        "loadingExperience": (
            {"overall_category": "FAST", "metrics": metrics} if field else {}
        ),
        "originLoadingExperience": {"overall_category": "FAST", "metrics": metrics},
        "lighthouseResult": {
            "lighthouseVersion": "13.4.1",
            "categories": {
                "performance": {"score": performance},
                "accessibility": {"score": 0.88},
                "best-practices": {"score": 1.0},
                "seo": {"score": 0.92},
            },
            "audits": audits
            if audits is not None
            else {
                "largest-contentful-paint": {"numericValue": lcp_ms},
                "cumulative-layout-shift": {"numericValue": cls},
                "total-blocking-time": {"numericValue": tbt_ms},
                "first-contentful-paint": {"numericValue": 900.0},
            },
        },
    }


def context_with_psi(payload, filename="good.html", strategy="mobile"):
    ctx = build_context(filename)
    ctx.extra["psi"] = {"strategies": {strategy: psi.parse(payload)}, "error": None}
    return ctx


# --- parsing ---------------------------------------------------------------


def test_parse_extracts_scores_and_lab_metrics():
    parsed = psi.parse(lighthouse_payload())
    assert parsed["scores"] == {
        "performance": 95,
        "accessibility": 88,
        "best-practices": 100,
        "seo": 92,
    }
    assert parsed["lab"]["lcp_ms"] == 1800
    # CLS is unitless and must survive with its decimals; rounding it to a
    # whole number would flatten every real value to 0.
    assert parsed["lab"]["cls"] == 0.02


def test_parse_rescales_crux_layout_shift():
    """CrUX reports CLS as an integer scaled by 100; 8 means 0.08."""
    parsed = psi.parse(lighthouse_payload())
    assert parsed["field"]["cls"] == 0.08
    assert parsed["field"]["lcp_ms"] == 2100


def test_parse_handles_a_url_with_no_field_data():
    """Most URLs have too little traffic for CrUX, which is not an error."""
    parsed = psi.parse(lighthouse_payload(field=False))
    assert parsed["field"] is None
    assert parsed["origin_field"] is not None


def test_opportunities_come_from_metric_savings_not_the_legacy_field():
    """Lighthouse 13 leaves ``overallSavingsMs`` at 0 on real opportunities.

    Reading only that field reported zero opportunities for pages scoring in
    the thirties, so extraction has to use ``metricSavings``.
    """
    parsed = psi.parse(
        lighthouse_payload(
            audits={
                "bootup-time": {
                    "id": "bootup-time",
                    "title": "Reduce JavaScript execution time",
                    "score": 0,
                    "metricSavings": {"TBT": 2250},
                    "details": {"type": "opportunity", "overallSavingsMs": 0},
                },
                "unused-javascript": {
                    "id": "unused-javascript",
                    "title": "Reduce unused JavaScript",
                    "score": 0.5,
                    "metricSavings": {},
                    "details": {"overallSavingsBytes": 621866},
                },
            }
        )
    )
    ids = [o["id"] for o in parsed["opportunities"]]
    assert ids == ["bootup-time", "unused-javascript"]
    assert parsed["opportunities"][0]["savings_ms"] == 2250
    assert parsed["opportunities"][1]["savings_bytes"] == 621866


def test_passing_and_inapplicable_audits_are_not_opportunities():
    parsed = psi.parse(
        lighthouse_payload(
            audits={
                "passing": {"id": "passing", "score": 1, "metricSavings": {"LCP": 500}},
                # score None means the audit does not apply to this page.
                "n/a": {"id": "n/a", "score": None, "metricSavings": {"LCP": 500}},
                "trivial": {"id": "t", "score": 0, "metricSavings": {"LCP": 20}},
            }
        )
    )
    assert parsed["opportunities"] == []


# --- checks ----------------------------------------------------------------


def test_vitals_checks_score_a_healthy_page():
    ctx = context_with_psi(lighthouse_payload())
    assert perf_checks.check_core_web_vitals(ctx).status == "good"
    assert perf_checks.check_lighthouse_performance(ctx).score == 95


def test_worst_metric_decides_the_vitals_verdict():
    """Passing Core Web Vitals needs every metric to pass, so a good CLS must
    not average away a failing LCP."""
    ctx = context_with_psi(lighthouse_payload(lcp_ms=7000.0, cls=0.0, tbt_ms=10.0))
    result = perf_checks.check_core_web_vitals(ctx)
    assert result.status == "critical"
    assert "LCP" in result.message


def test_mobile_is_scored_when_both_strategies_ran():
    """Google ranks on the mobile crawl, so desktop must not be what is scored."""
    ctx = build_context("good.html")
    ctx.extra["psi"] = {
        "strategies": {
            "desktop": psi.parse(lighthouse_payload(performance=0.99, lcp_ms=500.0)),
            "mobile": psi.parse(lighthouse_payload(performance=0.30, lcp_ms=9000.0)),
        },
        "error": None,
    }
    assert perf_checks.check_lighthouse_performance(ctx).score == 30
    assert perf_checks.check_core_web_vitals(ctx).status == "critical"


def test_field_data_falls_back_to_the_origin_and_says_so():
    ctx = context_with_psi(lighthouse_payload(field=False))
    result = perf_checks.check_field_vitals(ctx)
    assert result.value["scope"] == "this origin"


def test_psi_checks_are_informational_without_a_key():
    """A report run without PSI keeps the same shape, and is not penalised."""
    ctx = build_context("good.html")
    for check in (
        perf_checks.check_core_web_vitals,
        perf_checks.check_field_vitals,
        perf_checks.check_lighthouse_performance,
        perf_checks.check_lighthouse_categories,
    ):
        result = check(ctx)
        # "info" is what keeps these out of the score, so an absent key cannot
        # drag a report down or lift it up.
        assert result.status == "info", check.__name__
        assert result.value == {"available": False}


def test_low_traffic_page_is_not_penalised_for_missing_field_data():
    ctx = build_context("good.html")
    ctx.extra["psi"] = {
        "strategies": {"mobile": {"scores": {}, "lab": {}, "field": None,
                                  "origin_field": None, "opportunities": []}},
        "error": None,
    }
    assert perf_checks.check_field_vitals(ctx).status == "info"


# --- transport -------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_requests_every_category():
    """PSI returns performance alone unless the others are asked for."""
    with respx.mock:
        route = respx.get(psi.ENDPOINT).mock(
            return_value=httpx.Response(200, json=lighthouse_payload())
        )
        async with httpx.AsyncClient() as client:
            await psi.run(client, "https://example.com", "key", "mobile")
        requested = route.calls[0].request.url.params.get_list("category")
        assert set(requested) == set(psi.CATEGORIES)


@pytest.mark.asyncio
async def test_a_failing_strategy_does_not_lose_the_other():
    """Partial success is kept: one strategy failing must not discard both."""
    with respx.mock:
        respx.get(psi.ENDPOINT, params={"strategy": "mobile"}).mock(
            return_value=httpx.Response(200, json=lighthouse_payload())
        )
        respx.get(psi.ENDPOINT, params={"strategy": "desktop"}).mock(
            return_value=httpx.Response(429, json={"error": {"message": "Quota exceeded"}})
        )
        results, error = await psi.run_strategies(
            "https://example.com", "key", ["mobile", "desktop"]
        )
    assert set(results) == {"mobile"}
    assert error is None  # something succeeded, so the key is not at fault


@pytest.mark.asyncio
async def test_total_failure_reports_the_provider_error():
    with respx.mock:
        respx.get(psi.ENDPOINT).mock(
            return_value=httpx.Response(429, json={"error": {"message": "Quota exceeded"}})
        )
        results, error = await psi.run_strategies(
            "https://example.com", "key", ["mobile"]
        )
    assert results == {}
    assert "Quota exceeded" in error


@pytest.mark.asyncio
async def test_a_psi_outage_never_fails_the_analysis():
    """PSI is enrichment. Google being down must not cost the user a report."""
    with respx.mock:
        respx.get(psi.ENDPOINT).mock(side_effect=httpx.ConnectError("unreachable"))
        results, error = await psi.run_strategies(
            "https://example.com", "key", ["mobile"]
        )
    assert results == {}
    assert "unreachable" in error


@pytest.mark.asyncio
async def test_a_dead_key_stops_the_rest_of_the_audit():
    """Once Google says the key is out of quota, waiting runs are skipped
    instead of each calling Google to fail the same way."""
    semaphore, stop = asyncio.Semaphore(1), asyncio.Event()
    with respx.mock:
        route = respx.get(psi.ENDPOINT).mock(
            return_value=httpx.Response(429, json={"error": {"message": "Quota exceeded"}})
        )
        outcomes = await asyncio.gather(*(
            psi.run_strategies(f"https://example.com/{i}", "key", ["mobile"],
                               semaphore=semaphore, stop=stop)
            for i in range(3)
        ))
    assert route.call_count == 1
    assert "Quota exceeded" in outcomes[0][1]
    assert all(error.startswith("Skipped") for _, error in outcomes[1:])


@pytest.mark.asyncio
async def test_a_transient_failure_does_not_stop_the_audit():
    stop = asyncio.Event()
    with respx.mock:
        respx.get(psi.ENDPOINT).mock(return_value=httpx.Response(500, json={}))
        await psi.run_strategies("https://example.com", "key", ["mobile"], stop=stop)
    assert not stop.is_set()


def test_a_late_psi_result_rescores_the_page():
    """A crawl runs PageSpeed after the page analysis; folding it in must
    rescore the page exactly as if it had run inline."""
    ctx = build_context("good.html")
    checks = [check(ctx) for check in ALL_CHECKS]
    result = {"checks": [c.__dict__ for c in checks]}
    data = {"strategies": {"mobile": psi.parse(lighthouse_payload(performance=0.30,
                                                                  lcp_ms=9000.0))},
            "error": None}

    analyzer.apply_psi(result, data)

    by_id = {c["id"]: c for c in result["checks"]}
    assert by_id["lighthouse_performance"]["score"] == 30
    assert by_id["core_web_vitals"]["status"] == "critical"
    assert result["psi"] is data
    assert len(result["checks"]) == len(checks)

    ctx.extra["psi"] = data
    inline = analyzer._score_fields([check(ctx) for check in ALL_CHECKS])
    assert result["overall_score"] == inline["overall_score"]
    assert result["category_scores"] == inline["category_scores"]


def test_google_thresholds_are_unchanged():
    """These are Google's published boundaries, not ours to tune."""
    assert LCP_GOOD_MS == 2500
