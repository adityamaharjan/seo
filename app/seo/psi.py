"""Google PageSpeed Insights client.

PSI is the free route to Lighthouse and Core Web Vitals: 25k requests/day per
key, no paid tier. A key is mandatory in practice — keyless calls share an
anonymous quota pool that is permanently exhausted (HTTP 429), so every call
here carries a user-supplied key.

Two things this module deliberately does *not* do:

* Retry. A PSI call is 10-30 seconds of real Lighthouse execution, and an
  audit runs one per page per strategy. Retrying turns a slow audit into one
  that blows its wall-clock budget, so a failed run is reported as missing
  data and the analysis continues without it.
* Raise on failure. PSI is an enrichment, never a prerequisite: the whole
  report must still be produced when Google is slow, rate-limiting, or down.
  Only :func:`validate_key` raises, because there the caller asked
  specifically about the key.
"""
import asyncio
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# PSI returns the performance category alone unless the others are requested
# explicitly. They cost nothing extra — the same Lighthouse run produces them —
# so asking for all four is strictly better than asking for one.
CATEGORIES = ("performance", "accessibility", "best-practices", "seo")

# Lab metrics worth carrying out of the ~47 audits in a response. LCP, CLS and
# TBT are the three that map onto Core Web Vitals (TBT being the lab proxy for
# INP, which cannot be measured without real interaction).
_LAB_METRICS = {
    "largest-contentful-paint": "lcp_ms",
    "cumulative-layout-shift": "cls",
    "total-blocking-time": "tbt_ms",
    "first-contentful-paint": "fcp_ms",
    "speed-index": "speed_index_ms",
    "interactive": "tti_ms",
}

# CrUX field metrics, keyed by PSI's name. These are real Chrome users over the
# trailing 28 days, which is what Google actually ranks on — lab numbers are a
# reproducible proxy for them.
_FIELD_METRICS = {
    "LARGEST_CONTENTFUL_PAINT_MS": "lcp_ms",
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": "cls",
    "INTERACTION_TO_NEXT_PAINT": "inp_ms",
    "FIRST_CONTENTFUL_PAINT_MS": "fcp_ms",
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE": "ttfb_ms",
}

# Opportunities below this carry no practical advice: shaving 40ms is noise
# next to the effort of acting on it, and listing them buries the real ones.
_MIN_OPPORTUNITY_MS = 100
_MAX_OPPORTUNITIES = 8
# An audit scoring at or above this is passing; only failures are advice.
_OPPORTUNITY_FAIL_SCORE = 0.9
# Metrics in ``metricSavings`` measured in milliseconds. CLS also appears
# there but is unitless, so it cannot be ranked against the others.
_SAVINGS_MS_METRICS = ("LCP", "FCP", "TBT", "INP")

_VALIDATION_TARGET = "not-a-url"
_INVALID_KEY_MARKER = "api key not valid"


class PsiKeyInvalidError(ValueError):
    """The provider rejected the key itself."""


class PsiError(RuntimeError):
    """A PSI run failed for a reason that is not about the key."""


async def validate_key(api_key: str) -> None:
    """Check that PSI accepts a key. Raises :class:`PsiKeyInvalidError` if not.

    Any error that is *not* specifically about the key is treated as success:
    the malformed target is expected to be rejected, and quota or transport
    problems say nothing about whether the key is valid.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                ENDPOINT, params={"url": _VALIDATION_TARGET, "key": api_key}
            )
    except httpx.HTTPError as exc:
        logger.warning("psi key validation unreachable", extra={"error": str(exc)})
        return

    if response.status_code == 200:
        return

    message = ""
    try:
        message = (response.json().get("error", {}).get("message") or "").lower()
    except ValueError:
        return

    if _INVALID_KEY_MARKER in message:
        raise PsiKeyInvalidError(
            "Google rejected this key. Check that it is a PageSpeed Insights API "
            "key and that the API is enabled for its project."
        )


def _score(value: Any) -> int | None:
    """Lighthouse scores are 0-1 floats, or null for a category that errored."""
    return None if value is None else round(float(value) * 100)


def _lab_metrics(audits: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for audit_id, name in _LAB_METRICS.items():
        value = (audits.get(audit_id) or {}).get("numericValue")
        if value is not None:
            # CLS is unitless; everything else is milliseconds. Rounding CLS to
            # a whole number would flatten every real value to 0.
            out[name] = round(float(value), 3) if name == "cls" else round(float(value))
    return out


def _field_metrics(experience: dict | None) -> dict | None:
    """Flatten a CrUX ``loadingExperience`` block, or None when there is none.

    Most URLs have no field data: CrUX only reports origins and pages with
    enough real traffic to be statistically meaningful, so absence here is the
    normal case for a small site rather than an error.
    """
    if not experience:
        return None
    metrics = experience.get("metrics") or {}
    if not metrics:
        return None
    out: dict[str, Any] = {"overall_category": experience.get("overall_category")}
    for psi_name, name in _FIELD_METRICS.items():
        metric = metrics.get(psi_name)
        if not metric:
            continue
        percentile = metric.get("percentile")
        # CrUX reports CLS as an integer scaled by 100 (an 0.08 shift is 8).
        out[name] = percentile / 100 if name == "cls" and percentile else percentile
        out[f"{name}_category"] = metric.get("category")
    return out


def _opportunities(audits: dict) -> list[dict]:
    """Lighthouse's actionable fixes, largest estimated saving first.

    The saving comes from each audit's ``metricSavings``, not the older
    ``details.overallSavingsMs``. Lighthouse 13 leaves that legacy field at 0
    on audits that clearly do have headroom — a page scoring 35 reports zero
    opportunities by that measure — while ``metricSavings`` carries the real
    per-metric estimate. Bytes still come from the details block, since only
    the transfer-size audits report them.
    """
    found: list[dict] = []
    for audit in audits.values():
        score = audit.get("score")
        # None means "not applicable to this page", which is not a failure.
        if score is None or score >= _OPPORTUNITY_FAIL_SCORE:
            continue
        savings = audit.get("metricSavings") or (audit.get("details") or {}).get(
            "metricSavings"
        ) or {}
        by_metric = {
            metric: round(float(value))
            for metric in _SAVINGS_MS_METRICS
            if (value := savings.get(metric))
        }
        details = audit.get("details") or {}
        bytes_saved = round(float(details.get("overallSavingsBytes") or 0))
        best = max(by_metric.values(), default=0)
        if best < _MIN_OPPORTUNITY_MS and not bytes_saved:
            continue
        found.append(
            {
                "id": audit.get("id"),
                "title": audit.get("title"),
                "savings_ms": best,
                "savings_bytes": bytes_saved,
                "metrics": by_metric,
            }
        )
    found.sort(key=lambda o: (-o["savings_ms"], -o["savings_bytes"]))
    return found[:_MAX_OPPORTUNITIES]


def parse(payload: dict) -> dict:
    """Reduce a PSI response to the fields the checks consume.

    A full response is ~500KB of Lighthouse internals per strategy, and it is
    stored on every audited page. Keeping the parts that drive a check keeps a
    50-page audit's payload from dwarfing the analysis it belongs to.
    """
    lighthouse = payload.get("lighthouseResult") or {}
    audits = lighthouse.get("audits") or {}
    categories = lighthouse.get("categories") or {}
    return {
        "scores": {
            name: _score((categories.get(name) or {}).get("score"))
            for name in CATEGORIES
            if name in categories
        },
        "lab": _lab_metrics(audits),
        "field": _field_metrics(payload.get("loadingExperience")),
        # Origin-level field data stands in when the specific URL has too
        # little traffic of its own, which is the common case past the homepage.
        "origin_field": _field_metrics(payload.get("originLoadingExperience")),
        "opportunities": _opportunities(audits),
        "fetched_url": payload.get("id"),
        "lighthouse_version": lighthouse.get("lighthouseVersion"),
    }


async def run(
    client: httpx.AsyncClient, url: str, api_key: str, strategy: str
) -> dict:
    """Run one PSI analysis. Raises :class:`PsiError` if it does not complete."""
    params = [
        ("url", url),
        ("key", api_key),
        ("strategy", strategy),
        *(("category", c) for c in CATEGORIES),
    ]
    try:
        response = await client.get(ENDPOINT, params=params)
    except httpx.HTTPError as exc:
        raise PsiError(f"PageSpeed Insights was unreachable: {exc}") from exc

    if response.status_code != 200:
        message = ""
        try:
            message = (response.json().get("error", {}).get("message") or "").strip()
        except ValueError:
            message = response.text[:200]
        if _INVALID_KEY_MARKER in message.lower():
            raise PsiKeyInvalidError("Google rejected this PageSpeed key.")
        raise PsiError(message or f"PageSpeed Insights returned {response.status_code}.")

    try:
        return parse(response.json())
    except ValueError as exc:
        raise PsiError("PageSpeed Insights returned a malformed response.") from exc


async def run_strategies(
    url: str,
    api_key: str,
    strategies: list[str] | None = None,
    *,
    semaphore: asyncio.Semaphore | None = None,
) -> tuple[dict[str, dict], str | None]:
    """Run PSI for each strategy, returning ``(results, error)``.

    Partial success is kept: if mobile succeeds and desktop times out, the
    mobile data is still reported. ``error`` is set only when *nothing*
    succeeded, because its one consumer records it against the user's stored
    key — and a key that produced a usable result is not the thing that went
    wrong. Errors are returned rather than raised so a PSI problem never costs
    the caller their analysis.

    ``semaphore`` bounds concurrency across a whole audit, where one crawl can
    otherwise launch a PSI call per page at once.
    """
    wanted = strategies or settings.PSI_STRATEGIES
    results: dict[str, dict] = {}
    first_error: str | None = None

    async def one(client: httpx.AsyncClient, strategy: str) -> None:
        nonlocal first_error
        try:
            if semaphore is not None:
                async with semaphore:
                    results[strategy] = await run(client, url, api_key, strategy)
            else:
                results[strategy] = await run(client, url, api_key, strategy)
        except (PsiError, PsiKeyInvalidError) as exc:
            logger.warning(
                "psi run failed",
                extra={"url": url, "strategy": strategy, "error": str(exc)},
            )
            first_error = first_error or str(exc)

    timeout = httpx.Timeout(settings.PSI_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        await asyncio.gather(*(one(client, s) for s in wanted))

    return results, None if results else first_error
