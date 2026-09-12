"""Google PageSpeed Insights client.

PSI is the free route to Lighthouse and Core Web Vitals: 25k requests/day per
key, no paid tier. A key is mandatory in practice — keyless calls share an
anonymous quota pool that is permanently exhausted (HTTP 429), so every call
here carries a user-supplied key.

This module currently exposes key validation only; the measurement calls land
with the site-audit PSI phase.
"""
import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# PSI validates the key before it runs Lighthouse, so pairing a key with a
# deliberately malformed target returns in well under a second instead of
# waiting ~10-30s for a real audit. That makes a synchronous check on save
# viable, where a real measurement would make saving feel broken.
_VALIDATION_TARGET = "not-a-url"
_INVALID_KEY_MARKER = "api key not valid"


class PsiKeyInvalidError(ValueError):
    """The provider rejected the key itself."""


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
