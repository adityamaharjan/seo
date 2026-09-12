"""Fixed-window rate limiting, backed by the Redis instance ARQ already uses.

Only the unauthenticated endpoints need this: everything else is already
bounded by the per-user quota. The limiter fails open. If Redis is unreachable
the API keeps serving requests rather than locking every user out, and the
failure is logged.
"""
import ipaddress
from typing import Annotated

from fastapi import Depends, Request

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimitError(AppException):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests"


def _is_trusted_peer(host: str) -> bool:
    """True when the direct peer is a local reverse proxy.

    Forwarded-for headers are only believed in that case. A client connecting
    straight from the internet has a public peer address, so a header it forges
    is ignored and it cannot escape its own bucket.
    """
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if _is_trusted_peer(peer):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return peer


async def enforce(request: Request, *, bucket: str, limit: int, window: int) -> None:
    """Count one hit against ``bucket`` and raise 429 past ``limit``."""
    if not settings.RATE_LIMIT_ENABLED:
        return

    redis = getattr(request.app.state, "arq", None)
    if redis is None or not hasattr(redis, "incr"):
        return  # no Redis wired up (e.g. tests): nothing to count against

    key = f"ratelimit:{bucket}"
    try:
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = await pipe.execute()
        if ttl is None or ttl < 0:
            await redis.expire(key, window)
            ttl = window
    except Exception as exc:  # fail open, never block traffic on a Redis fault
        logger.warning("rate limit check failed", extra={"error": str(exc)})
        return

    if count > limit:
        raise RateLimitError(
            "Too many requests. Please slow down and try again shortly.",
            details={"limit": limit, "window_seconds": window},
            headers={"Retry-After": str(max(1, int(ttl)))},
        )


def limit_by_ip(*, scope: str, limit: int, window: int):
    """Build a dependency that rate-limits an endpoint per client IP."""

    async def dependency(request: Request) -> None:
        await enforce(
            request, bucket=f"{scope}:ip:{client_ip(request)}", limit=limit, window=window
        )

    return dependency


async def limit_login_account(request: Request, email: str) -> None:
    """Second bucket for login, keyed on the account being targeted.

    Stops a distributed attempt from spreading guesses for one account across
    many source addresses.
    """
    await enforce(
        request,
        bucket=f"login:account:{email.strip().lower()}",
        limit=settings.LOGIN_RATE_LIMIT,
        window=settings.LOGIN_RATE_WINDOW_SECONDS,
    )


LoginIPLimit = Annotated[
    None,
    Depends(
        limit_by_ip(
            scope="login",
            limit=settings.LOGIN_RATE_LIMIT,
            window=settings.LOGIN_RATE_WINDOW_SECONDS,
        )
    ),
]
SignupIPLimit = Annotated[
    None,
    Depends(
        limit_by_ip(
            scope="signup",
            limit=settings.SIGNUP_RATE_LIMIT,
            window=settings.SIGNUP_RATE_WINDOW_SECONDS,
        )
    ),
]
RefreshIPLimit = Annotated[
    None,
    Depends(
        limit_by_ip(
            scope="refresh",
            limit=settings.LOGIN_RATE_LIMIT * 3,
            window=settings.LOGIN_RATE_WINDOW_SECONDS,
        )
    ),
]
