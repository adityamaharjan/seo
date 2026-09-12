"""Weighted category scoring and grading.

Each check yields a 0-100 score. Within a category, scores are combined using
the per-check weights in :data:`app.seo.constants.CHECK_WEIGHTS`; categories
then combine using :data:`app.seo.constants.CATEGORY_WEIGHTS`. Informational
checks (status == "info") do not drag the score down.

The checks in :data:`app.seo.constants.SCORE_CAPS` cap the overall score when
they come back critical, rather than being averaged away by everything the
page does get right.
"""
from collections import defaultdict
from dataclasses import dataclass, field, replace

from app.seo.constants import CATEGORY_WEIGHTS, CHECK_WEIGHTS, SCORE_CAPS
from app.seo.types import CheckResult

STATUSES = ("critical", "warning", "good", "info")


@dataclass
class ScoreBreakdown:
    overall: int
    grade: str
    categories: list[dict]
    issue_counts: dict[str, int]
    # What the page would score with the capping checks fixed and nothing else
    # changed. Equal to ``overall`` when nothing capped.
    uncapped_overall: int
    capped_by: list[str] = field(default_factory=list)


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


def count_statuses(checks: list[CheckResult]) -> dict[str, int]:
    counts = dict.fromkeys(STATUSES, 0)
    for c in checks:
        counts[c.status] = counts.get(c.status, 0) + 1
    return counts


def _weighted_score(checks: list[CheckResult]) -> tuple[int, list[dict]]:
    """Combine checks into per-category scores and one overall score."""
    by_cat: dict[str, list[CheckResult]] = defaultdict(list)
    for c in checks:
        by_cat[c.category].append(c)

    category_scores: list[dict] = []
    weighted_sum = 0.0
    active_weight = 0.0

    for category, weight in CATEGORY_WEIGHTS.items():
        cat_checks = by_cat.get(category, [])
        scoring = [c for c in cat_checks if c.status != "info"]
        if not scoring:
            cat_score = 100  # nothing to penalize
        else:
            total = sum(CHECK_WEIGHTS.get(c.id, 1.0) for c in scoring)
            cat_score = round(
                sum(c.score * CHECK_WEIGHTS.get(c.id, 1.0) for c in scoring) / total
            )
        category_scores.append(
            {
                "category": category,
                "score": cat_score,
                "grade": grade(cat_score),
                "weight": weight,
                "checks": [c.id for c in cat_checks],
            }
        )
        weighted_sum += cat_score * weight
        active_weight += weight

    overall = round(weighted_sum / active_weight) if active_weight else 0
    return overall, category_scores


def score_categories(checks: list[CheckResult]) -> ScoreBreakdown:
    overall, category_scores = _weighted_score(checks)
    capped_by = [c.id for c in checks if c.status == "critical" and c.id in SCORE_CAPS]
    capped = min([overall, *(SCORE_CAPS[check_id] for check_id in capped_by)])

    # "Fixing that alone would take this page to X" has to actually be true, so
    # X is recomputed with the capping checks passing. Reporting the raw
    # weighted score here understated it: a capping check also drags its own
    # category, so the page was being penalized twice for one fault and the
    # promised number was lower than the fix would really deliver.
    if capped_by:
        repaired = [
            replace(c, status="good", score=100) if c.id in capped_by else c
            for c in checks
        ]
        uncapped, _ = _weighted_score(repaired)
    else:
        uncapped = overall

    return ScoreBreakdown(
        overall=capped,
        grade=grade(capped),
        categories=category_scores,
        issue_counts=count_statuses(checks),
        uncapped_overall=uncapped,
        capped_by=capped_by,
    )
