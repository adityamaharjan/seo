"""Keyword targeting: how well a page targets terms its owner named.

This is a *separate feature* from the page audit, not a check inside it. The
audit answers "is this page technically healthy", which is a property of the
URL alone; keyword targeting answers "is this page aimed at the right terms",
which depends entirely on what the submitter typed. Folding the second into the
first meant the same URL scored differently depending on whether the keyword
box was filled in, which is not a defensible thing for a health score to do.

Each keyword is scored on **placement**: where it appears, weighted by how much
that location influences relevance. Density is reported but only penalized when
it crosses into stuffing, because repetition is the easiest signal to fake and
the least valuable.
"""
import re
from urllib.parse import urlparse

from app.seo.constants import (
    KEYWORD_DENSITY_MAX,
    KEYWORD_DENSITY_MIN_SAMPLE,
    KEYWORD_OPENING_WORDS,
    KEYWORD_PLACEMENT_LABELS,
    KEYWORD_PLACEMENT_WEIGHTS,
)
from app.seo.types import AnalysisContext
from app.seo.text import attr

_GOOD_SCORE = 70
_WARNING_SCORE = 40
# Penalty applied once a keyword crosses from repetition into stuffing.
_STUFFING_PENALTY = 15
# Shortest word that may match with a suffix, so "car" never matches "carpet".
_STEM_MIN_LENGTH = 4


def grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _patterns(keyword: str) -> tuple[re.Pattern[str], re.Pattern[str]]:
    """Exact-phrase and inflection-tolerant patterns for one keyword.

    Targeting "urban garden" should get credit for a title saying "urban
    gardening" — the same term, inflected — so the loose pattern lets each word
    carry a suffix. That is only allowed on words long enough for it to mean
    something, otherwise "car" would match "carpet".

    Built per call rather than cached: keywords are user input, so a cache keyed
    on them would grow without bound.
    """
    words = keyword.split()
    exact = re.compile(
        r"\b" + r"\W+".join(re.escape(word) for word in words) + r"\b", re.IGNORECASE
    )
    loose = re.compile(
        r"\b"
        + r"\W+".join(
            re.escape(word) + (r"\w*" if len(word) >= _STEM_MIN_LENGTH else "")
            for word in words
        ),
        re.IGNORECASE,
    )
    return exact, loose


def _applicable_slots(ctx: AnalysisContext) -> dict[str, bool]:
    """Which placements this page could plausibly have at all.

    A page with no images cannot put a keyword in image alt text, and a page
    with no subheadings cannot put one in an H2. Counting those as misses made
    a perfect score unreachable in practice: a well-optimized page topped out
    around 85, so naming keywords almost always looked like a failure.
    """
    soup = ctx.soup
    slug = urlparse(ctx.fetch.final_url).path.strip("/")
    return {
        "title": True,
        "h1": True,
        "meta_description": True,
        "first_paragraph": ctx.word_count > 0,
        "subheading": bool(soup.find(["h2", "h3", "h4", "h5", "h6"])),
        # The homepage has no slug to put a keyword in; that is not a fault.
        "url_slug": bool(slug),
        "image_alt": bool(soup.find("img")),
    }


def _placements(ctx: AnalysisContext, keyword: str) -> dict[str, str | None]:
    """Where the keyword appears, and whether exactly or as an inflection."""
    soup = ctx.soup
    exact, loose = _patterns(keyword)

    def match(text: str | None) -> str | None:
        if not text:
            return None
        if exact.search(text):
            return "exact"
        return "partial" if loose.search(text) else None

    def best(texts: list[str]) -> str | None:
        found = [match(text) for text in texts]
        if "exact" in found:
            return "exact"
        return "partial" if "partial" in found else None

    title = soup.find("title")
    h1 = soup.find("h1")
    description = soup.find("meta", attrs={"name": "description"})
    slug = _normalize(urlparse(ctx.fetch.final_url).path.replace("-", " ").replace("/", " "))
    opening = " ".join(ctx.clean_text.split()[:KEYWORD_OPENING_WORDS])

    return {
        "title": match(title.get_text(strip=True) if title else None),
        "h1": match(h1.get_text(strip=True) if h1 else None),
        "meta_description": match(
            attr(description, "content") if description else None
        ),
        "first_paragraph": match(opening),
        "subheading": best(
            [tag.get_text(strip=True) for tag in soup.find_all(["h2", "h3", "h4", "h5", "h6"])]
        ),
        "url_slug": match(slug),
        "image_alt": best([attr(img, "alt") for img in soup.find_all("img")]),
    }


def _density(ctx: AnalysisContext, keyword: str) -> float:
    """Percentage of body words taken up by this phrase, inflections included."""
    if not ctx.word_count:
        return 0.0
    _, loose = _patterns(keyword)
    occurrences = len(loose.findall(ctx.clean_text))
    phrase_words = len(keyword.split())
    return round((occurrences * phrase_words / ctx.word_count) * 100, 2)


def _score_keyword(ctx: AnalysisContext, keyword: str, applicable: dict[str, bool]) -> dict:
    placements = _placements(ctx, keyword)
    # Only placements the page could actually have count toward the total, so
    # the score is a percentage of the opportunities that exist on this page.
    available = sum(
        weight for slot, weight in KEYWORD_PLACEMENT_WEIGHTS.items() if applicable[slot]
    )
    # An inflected match is worth half — it counts, but the exact phrase counts
    # for more.
    earned = sum(
        weight if placements[slot] == "exact" else weight / 2
        for slot, weight in KEYWORD_PLACEMENT_WEIGHTS.items()
        if applicable[slot] and placements[slot]
    )
    score = round(100 * earned / available) if available else 0

    density = _density(ctx, keyword)
    # Below the sample floor a single mention swamps the percentage — two words
    # on a 15-word page reads as 26% — so stuffing is not judged there. The thin
    # content is the real problem and the audit's word_count check reports it.
    stuffed = (
        density > KEYWORD_DENSITY_MAX and ctx.word_count >= KEYWORD_DENSITY_MIN_SAMPLE
    )
    if stuffed:
        # Over-repetition is a liability, not a bonus, so it costs rather than adds.
        score = max(0, score - _STUFFING_PENALTY)

    missing = [
        slot
        for slot in sorted(
            KEYWORD_PLACEMENT_WEIGHTS, key=lambda s: KEYWORD_PLACEMENT_WEIGHTS[s], reverse=True
        )
        if applicable[slot] and not placements[slot]
    ]
    return {
        "keyword": keyword,
        "score": score,
        "grade": grade(score),
        "found_in": {slot: kind for slot, kind in placements.items() if kind},
        "missing_from": missing,
        "not_applicable": [slot for slot, ok in applicable.items() if not ok],
        "density_pct": density,
        "over_used": stuffed,
    }


def _recommend(results: list[dict]) -> str | None:
    """Name the single most valuable fix, not every possible one."""
    worst = min(results, key=lambda r: r["score"])
    if worst["over_used"]:
        return (
            f"'{worst['keyword']}' appears too often ({worst['density_pct']}% of the "
            "page). Cut the repetition and rely on placement instead."
        )
    if not worst["missing_from"]:
        return None
    top_misses = [KEYWORD_PLACEMENT_LABELS[slot] for slot in worst["missing_from"][:2]]
    return f"Add '{worst['keyword']}' to the {' and '.join(top_misses)}."


def analyze_keywords(ctx: AnalysisContext) -> dict | None:
    """Build the standalone keyword report, or None if no keywords were given."""
    keywords = ctx.target_keywords
    if not keywords:
        return None

    applicable = _applicable_slots(ctx)
    results = [_score_keyword(ctx, keyword, applicable) for keyword in keywords]
    average = round(sum(r["score"] for r in results) / len(results))

    if average >= _GOOD_SCORE:
        status = "good"
    elif average >= _WARNING_SCORE:
        status = "warning"
    else:
        status = "critical"

    placed = sum(1 for r in results if r["score"] >= _GOOD_SCORE)
    message = (
        f"{placed} of {len(results)} target keywords are well placed."
        if len(results) > 1
        else f"'{results[0]['keyword']}' scores {average}/100 on placement."
    )

    return {
        "score": average,
        "grade": grade(average),
        "status": status,
        "message": message,
        "recommendation": None if status == "good" else _recommend(results),
        "keywords": results,
        # Shipped with the report so the UI can render a placement matrix
        # without keeping its own copy of these constants in sync.
        "placement_weights": dict(KEYWORD_PLACEMENT_WEIGHTS),
        "placement_labels": dict(KEYWORD_PLACEMENT_LABELS),
    }
