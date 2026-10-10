"""SEO check accuracy tests against committed fixture HTML (no network)."""
from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app.seo.checks import ALL_CHECKS
from app.seo.checks import content as content_checks
from app.seo.checks import headings as heading_checks
from app.seo import keywords as keyword_feature
from app.seo.checks import meta as meta_checks
from app.seo.checks import technical as technical_checks
from app.seo.constants import SCORE_CAPS
from app.seo.scoring import score_categories
from app.seo.text import extract_clean_text, tokenize
from app.seo.types import AnalysisContext, FetchResult

FIXTURES = Path(__file__).parent / "fixtures"


def build_context(
    filename: str,
    *,
    final_url="https://example.com/page",
    target_keywords: list[str] | None = None,
) -> AnalysisContext:
    html = (FIXTURES / filename).read_text(encoding="utf-8")
    content = html.encode("utf-8")
    soup = BeautifulSoup(content, "lxml")
    clean = extract_clean_text(soup)
    tokens = tokenize(clean)
    fetch = FetchResult(
        requested_url=final_url,
        final_url=final_url,
        domain="example.com",
        status_code=200,
        ok=True,
        content=content,
        text=html,
        headers={"content-encoding": "gzip", "strict-transport-security": "max-age=1"},
        ttfb_ms=120.0,
        load_time_ms=450.0,
        transfer_size_bytes=len(content),
        html_size_bytes=len(content),
        compressed=True,
        redirect_count=0,
    )
    return AnalysisContext(
        fetch=fetch,
        soup=soup,
        clean_text=clean,
        tokens=tokens,
        word_count=len(tokens),
        target_keywords=list(target_keywords or []),
    )


def run_all(ctx: AnalysisContext) -> dict:
    return {c.id: c for c in (check(ctx) for check in ALL_CHECKS)}


@pytest.mark.parametrize("filename", ["good.html", "bad.html"])
def test_all_checks_run_without_error(filename):
    results = run_all(build_context(filename))
    assert len(results) >= 20  # every check produced a result
    for r in results.values():
        assert 0 <= r.score <= 100
        assert r.status in {"good", "warning", "critical", "info"}


def test_good_page_scores_high():
    ctx = build_context("good.html")
    checks = list(run_all(ctx).values())
    breakdown = score_categories(checks)
    assert breakdown.overall >= 75
    assert breakdown.grade in {"A", "B", "C"}
    assert len(breakdown.categories) == 8
    assert breakdown.capped_by == []
    assert breakdown.uncapped_overall == breakdown.overall


def test_heavier_checks_move_the_category_score_further():
    """A failing title must cost far more than a failing Twitter card."""
    ctx = build_context("good.html")
    checks = list(run_all(ctx).values())

    def meta_score_with_failure(check_id: str) -> int:
        broken = [
            replace(c, status="critical", score=0) if c.id == check_id else c
            for c in checks
        ]
        categories = score_categories(broken).categories
        return next(c["score"] for c in categories if c["category"] == "meta")

    baseline = next(
        c["score"] for c in score_categories(checks).categories if c["category"] == "meta"
    )
    title_cost = baseline - meta_score_with_failure("title_tag")
    twitter_cost = baseline - meta_score_with_failure("twitter_card")

    assert title_cost > twitter_cost * 5
    assert twitter_cost > 0


def test_noindex_caps_the_overall_score():
    ctx = build_context("good.html")
    checks = [
        replace(c, status="critical", score=0) if c.id == "meta_robots" else c
        for c in run_all(ctx).values()
    ]
    breakdown = score_categories(checks)

    assert breakdown.overall == SCORE_CAPS["meta_robots"]
    assert breakdown.grade == "F"
    assert breakdown.capped_by == ["meta_robots"]
    # The page is otherwise healthy, which is exactly why the cap exists.
    assert breakdown.uncapped_overall > breakdown.overall


def test_lowest_cap_wins_when_several_apply():
    ctx = build_context("good.html", final_url="http://example.com/page")
    checks = [
        replace(c, status="critical", score=0) if c.id == "meta_robots" else c
        for c in run_all(ctx).values()
    ]
    breakdown = score_categories(checks)

    assert set(breakdown.capped_by) == {"meta_robots", "https"}
    assert breakdown.overall <= SCORE_CAPS["meta_robots"]


def test_issue_counts_tally_every_check():
    ctx = build_context("bad.html")
    checks = list(run_all(ctx).values())
    breakdown = score_categories(checks)

    assert sum(breakdown.issue_counts.values()) == len(checks)
    assert breakdown.issue_counts["critical"] > 0
    assert set(breakdown.issue_counts) == {"critical", "warning", "good", "info"}


def test_bad_page_flags_problems():
    results = run_all(build_context("bad.html"))
    assert results["title_tag"].status != "good"  # title "hi" too short
    assert results["meta_description"].status == "critical"  # missing
    assert results["h1_heading"].status == "warning"  # two H1s
    assert results["mobile_viewport"].status == "critical"  # missing viewport
    assert results["image_alt"].status in {"warning", "critical"}  # no alt text
    assert results["word_count"].status in {"warning", "critical"}  # thin content


def test_title_length_thresholds():
    ctx = build_context("good.html")
    res = meta_checks.check_title(ctx)
    assert res.status == "good"
    assert 30 <= res.value["length"] <= 65


def test_keyword_report_is_absent_without_target_keywords():
    """The common case: no keywords given, so the feature produces nothing."""
    assert keyword_feature.analyze_keywords(build_context("good.html")) is None


def test_keyword_targeting_is_not_part_of_the_audit_score():
    """The page audit must score the same whether or not keywords were named.

    This is the whole point of the split: page health is a property of the URL,
    so typing keywords into a box cannot change it.
    """
    plain = list(run_all(build_context("good.html")).values())
    targeted = list(
        run_all(build_context("good.html", target_keywords=["urban garden"])).values()
    )

    assert score_categories(plain).overall == score_categories(targeted).overall
    assert not any(c.id == "keyword_targeting" for c in plain)


def test_keyword_targeting_rewards_placement():
    """A keyword in the title and H1 must beat one that appears nowhere."""
    ctx = build_context("good.html", target_keywords=["urban garden"])
    present = keyword_feature.analyze_keywords(ctx)["keywords"][0]

    absent_ctx = build_context("good.html", target_keywords=["snowmobile repair"])
    absent = keyword_feature.analyze_keywords(absent_ctx)["keywords"][0]

    assert present["score"] > absent["score"]
    assert absent["score"] == 0
    assert absent["found_in"] == {}
    assert "title" in absent["missing_from"]


def test_keyword_targeting_credits_inflections_as_partial():
    """Targeting "urban garden" on a page about "urban gardening" must count."""
    ctx = build_context("good.html", target_keywords=["urban garden"])
    result = keyword_feature.analyze_keywords(ctx)["keywords"][0]

    # The fixture's title and H1 both say "Urban Gardening".
    assert result["found_in"]["title"] == "partial"
    assert result["found_in"]["h1"] == "partial"

    exact_ctx = build_context("good.html", target_keywords=["urban gardening"])
    exact = keyword_feature.analyze_keywords(exact_ctx)["keywords"][0]
    assert exact["found_in"]["title"] == "exact"
    assert exact["score"] > result["score"]  # exact beats inflected


def test_placements_the_page_cannot_have_are_not_counted_as_misses():
    """A page with no images cannot put a keyword in alt text.

    Scoring that as a miss is what made 100 unreachable, so an absent slot is
    dropped from the denominator instead of counted against the keyword.
    """
    ctx = build_context("good.html", target_keywords=["urban gardening"])
    for img in ctx.soup.find_all("img"):
        img.decompose()

    result = keyword_feature.analyze_keywords(ctx)["keywords"][0]
    assert "image_alt" in result["not_applicable"]
    assert "image_alt" not in result["missing_from"]


def test_short_words_do_not_match_by_prefix():
    """A 3-letter keyword must not match a longer word that starts with it."""
    ctx = build_context("good.html", target_keywords=["car"])
    result = keyword_feature.analyze_keywords(ctx)["keywords"][0]
    assert result["score"] == 0  # "carefully" must not count as "car"


def test_keyword_targeting_reports_each_keyword():
    ctx = build_context("good.html", target_keywords=["urban garden", "balcony"])
    report = keyword_feature.analyze_keywords(ctx)
    assert [k["keyword"] for k in report["keywords"]] == ["urban garden", "balcony"]
    assert report["score"] == round(sum(k["score"] for k in report["keywords"]) / 2)


def test_keyword_targeting_penalizes_stuffing():
    ctx = build_context("good.html", target_keywords=["garden"])
    ctx.clean_text = "garden " * 200
    ctx.word_count = 200

    report = keyword_feature.analyze_keywords(ctx)
    result = report["keywords"][0]

    assert result["over_used"] is True
    assert result["density_pct"] > 3.0
    assert "too often" in report["recommendation"]


def test_stuffing_is_not_judged_on_a_tiny_page():
    """Two mentions on a 15-word page reads as 26% density; that is not stuffing."""
    ctx = build_context("good.html", target_keywords=["garden"])
    ctx.clean_text = "a garden and a garden again " * 2
    ctx.word_count = 14

    result = keyword_feature.analyze_keywords(ctx)["keywords"][0]

    assert result["density_pct"] > 3.0  # still reported
    assert result["over_used"] is False  # but not penalized


def test_keyword_matching_ignores_case_and_spacing():
    ctx = build_context("good.html", target_keywords=["URBAN    Garden"])
    result = keyword_feature.analyze_keywords(ctx)["keywords"][0]
    assert result["score"] > 0


def test_typo_detection():
    ctx = build_context("bad.html")
    res = content_checks.check_typos(ctx)
    assert res.status == "warning"
    assert "teh" in res.value or "recieve" in res.value


def test_https_check_flags_http():
    ctx = build_context("good.html", final_url="http://example.com/page")
    assert technical_checks.check_https(ctx).status == "critical"


def test_heading_hierarchy_good_page():
    ctx = build_context("good.html")
    res = heading_checks.check_heading_hierarchy(ctx)
    assert res.status == "good"


def test_attr_reads_single_and_multi_valued_attributes():
    from app.seo.text import attr

    soup = BeautifulSoup('<link rel="icon shortcut" href=" /f.ico "><meta>', "lxml")
    assert attr(soup.find("link"), "rel") == "icon shortcut"  # BS4 gives a list here
    assert attr(soup.find("link"), "href") == " /f.ico "
    assert attr(soup.find("meta"), "content") == ""
    assert attr(None, "content") == ""
