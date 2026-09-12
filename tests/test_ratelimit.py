"""Rate limiting on the unauthenticated endpoints."""
import pytest

from app.core.ratelimit import RateLimitError, client_ip, enforce


class FakeRedis:
    """Minimal stand-in supporting the INCR/TTL/EXPIRE the limiter uses."""

    def __init__(self, *, broken: bool = False) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.broken = broken

    def pipeline(self):
        redis = self

        class _Pipe:
            def __init__(self):
                self.ops = []

            def incr(self, key):
                self.ops.append(("incr", key))

            def ttl(self, key):
                self.ops.append(("ttl", key))

            async def execute(self):
                if redis.broken:
                    raise ConnectionError("redis is down")
                out = []
                for op, key in self.ops:
                    if op == "incr":
                        redis.counts[key] = redis.counts.get(key, 0) + 1
                        out.append(redis.counts[key])
                    else:
                        out.append(redis.ttls.get(key, -1))
                return out

        return _Pipe()

    async def incr(self, key):  # presence is what the limiter probes for
        raise NotImplementedError

    async def expire(self, key, seconds):
        self.ttls[key] = seconds


class FakeRequest:
    def __init__(self, redis=None, peer="93.184.216.34", headers=None):
        self.headers = headers or {}

        class _State:
            pass

        state = _State()
        if redis is not None:
            state.arq = redis

        class _App:
            pass

        app = _App()
        app.state = state
        self.app = app

        class _Client:
            host = peer

        self.client = _Client()


@pytest.mark.asyncio
async def test_requests_are_blocked_past_the_limit():
    redis = FakeRedis()
    request = FakeRequest(redis)

    for _ in range(3):
        await enforce(request, bucket="login:ip:a", limit=3, window=60)

    with pytest.raises(RateLimitError) as excinfo:
        await enforce(request, bucket="login:ip:a", limit=3, window=60)
    assert excinfo.value.status_code == 429
    assert "Retry-After" in excinfo.value.headers


@pytest.mark.asyncio
async def test_buckets_are_independent():
    redis = FakeRedis()
    request = FakeRequest(redis)
    for _ in range(3):
        await enforce(request, bucket="login:ip:a", limit=3, window=60)
    # A different key must start from zero.
    await enforce(request, bucket="login:ip:b", limit=3, window=60)


@pytest.mark.asyncio
async def test_limiter_fails_open_when_redis_is_down():
    """A Redis outage must not lock every user out of the API."""
    request = FakeRequest(FakeRedis(broken=True))
    for _ in range(50):
        await enforce(request, bucket="login:ip:a", limit=1, window=60)


@pytest.mark.asyncio
async def test_limiter_is_inert_without_redis():
    request = FakeRequest(None)
    await enforce(request, bucket="login:ip:a", limit=1, window=60)
    await enforce(request, bucket="login:ip:a", limit=1, window=60)


def test_forwarded_header_is_ignored_from_a_public_peer():
    """Otherwise a direct caller could forge a fresh bucket per request."""
    request = FakeRequest(peer="93.184.216.34", headers={"x-forwarded-for": "1.2.3.4"})
    assert client_ip(request) == "93.184.216.34"


def test_forwarded_header_is_used_behind_a_local_proxy():
    request = FakeRequest(
        peer="127.0.0.1", headers={"x-forwarded-for": "1.2.3.4, 10.0.0.1"}
    )
    assert client_ip(request) == "1.2.3.4"
