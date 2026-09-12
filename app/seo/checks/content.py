"""Content quality checks: depth, keywords, readability, stopwords, typos."""
import re

from app.seo.constants import (
    COMMON_TYPOS,
    GOOD_CONTENT_WORDS,
    STOPWORD_DENSITY_WARN,
    THIN_CONTENT_WORDS,
)
from app.seo.readability import analyze_readability
from app.seo.text import stopword_density
from app.seo.types import AnalysisContext, CheckResult

CATEGORY = "content"


def check_word_count(ctx: AnalysisContext) -> CheckResult:
    wc = ctx.word_count
    if wc >= GOOD_CONTENT_WORDS:
        status, score, msg = "good", 100, "Content depth is excellent."
    elif wc >= THIN_CONTENT_WORDS:
        status, score, msg = "good", 85, "Content depth is sufficient."
    elif wc >= 150:
        status, score, msg = "warning", 60, "Content may be too thin."
    else:
        status, score, msg = "critical", 30, "Content is very thin."
    return CheckResult(
        "word_count", CATEGORY, status, score, "Content length",
        f"{msg} ({wc} significant words)", value=wc,
        recommendation=None if status == "good" else "Aim for 300+ meaningful words.",
    )


def check_readability(ctx: AnalysisContext) -> CheckResult:
    r = analyze_readability(ctx.clean_text)
    if r.word_count == 0:
        return CheckResult(
            "readability", CATEGORY, "warning", 40, "Readability",
            "Not enough text to assess readability.", value=None,
        )
    if r.flesch_reading_ease >= 60:
        status, score = "good", 100
    elif r.flesch_reading_ease >= 40:
        status, score = "warning", 75
    else:
        status, score = "warning", 55
    return CheckResult(
        "readability", CATEGORY, status, score, "Readability",
        f"Flesch reading ease {r.flesch_reading_ease} ({r.interpretation}).",
        value={
            "flesch_reading_ease": r.flesch_reading_ease,
            "flesch_kincaid_grade": r.flesch_kincaid_grade,
            "avg_words_per_sentence": r.avg_words_per_sentence,
            "sentence_count": r.sentence_count,
        },
        recommendation=(
            "Use shorter sentences and simpler words." if status != "good" else None
        ),
    )


def check_stopword_density(ctx: AnalysisContext) -> CheckResult:
    pct = stopword_density(ctx.clean_text)
    status = "good" if pct < STOPWORD_DENSITY_WARN else "warning"
    return CheckResult(
        "stopword_density", CATEGORY, status, 100 if status == "good" else 70,
        "Stop-word density", f"{pct}% of words are stop words.", value=pct,
        recommendation=None if status == "good" else "Add more substantive content.",
    )


def check_typos(ctx: AnalysisContext) -> CheckResult:
    words = set(re.findall(r"[a-z]+", ctx.clean_text.lower()))
    found = sorted(words & COMMON_TYPOS)
    if not found:
        return CheckResult(
            "typos", CATEGORY, "good", 100, "Spelling", "No common typos detected.",
            value=[],
        )
    return CheckResult(
        "typos", CATEGORY, "warning", 70, "Spelling",
        f"Detected {len(found)} potential typo(s).", value=found,
        recommendation="Proofread the content; fix flagged misspellings.",
    )


CHECKS = [
    check_word_count,
    check_readability,
    check_stopword_density,
    check_typos,
]
