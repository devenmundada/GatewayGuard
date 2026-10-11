"""Behaviour when dependencies fail."""
from unittest.mock import AsyncMock, patch

import pytest
import redis as redis_lib
from sqlalchemy.exc import OperationalError

from app.core.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState
from app.core.rate_limiter import RateLimiter


class TestDatabaseOutage:
    async def test_login_returns_503_not_a_fake_401(self, client, test_user):
        await client.post("/api/v1/auth/register", json=test_user)
        boom = OperationalError("SELECT 1", {}, ConnectionRefusedError("connect call failed"))
        with patch("app.db.crud.get_user_by_email", new=AsyncMock(side_effect=boom)):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": test_user["email"], "password": test_user["password"]},
            )
        assert response.status_code == 503
        assert response.headers["retry-after"] == "5"

    async def test_connection_refused_from_driver_is_503(self, client, test_user):
        with patch(
            "app.db.crud.user_exists", new=AsyncMock(side_effect=ConnectionRefusedError())
        ):
            response = await client.post("/api/v1/auth/register", json=test_user)
        assert response.status_code == 503

    async def test_register_does_not_create_phantom_user(self, client, test_user):
        with patch(
            "app.db.crud.user_exists", new=AsyncMock(side_effect=ConnectionRefusedError())
        ):
            await client.post("/api/v1/auth/register", json=test_user)
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )
        assert login.status_code == 401  # nothing was silently stored in memory


class _FailingRedis:
    """Looks like redis.Redis but every command fails."""

    def register_script(self, _src):
        def run(**_kwargs):
            raise redis_lib.ConnectionError("down")
        return run


class _FlakyRedis:
    def __init__(self):
        self.up = False
        self.counts = {}

    def register_script(self, _src):
        def run(keys, args):
            if not self.up:
                raise redis_lib.ConnectionError("down")
            self.counts[keys[0]] = self.counts.get(keys[0], 0) + 1
            return [self.counts[keys[0]], int(args[0])]
        return run


class TestRedisOutage:
    def test_limiter_falls_back_to_memory_and_still_limits(self):
        limiter = RateLimiter(_FailingRedis())
        results = [limiter.check("k", 5, 60).allowed for _ in range(8)]
        assert results == [True] * 5 + [False] * 3

    def test_breaker_opens_then_limiter_reconnects_without_restart(self):
        redis = _FlakyRedis()
        breaker = CircuitBreaker("t", CircuitConfig(failure_threshold=2, recovery_timeout=0))
        limiter = RateLimiter(redis, breaker)

        limiter.check("k", 5, 60)
        limiter.check("k", 5, 60)
        assert breaker.state == CircuitState.OPEN
        assert "k" in limiter.memory_store  # served from memory meanwhile

        redis.up = True  # Redis comes back
        limiter.check("k", 5, 60)  # recovery_timeout=0: half-open trial succeeds
        assert breaker.state == CircuitState.CLOSED
        assert redis.counts["k"] == 1  # and Redis is being used again

    def test_open_breaker_skips_redis_entirely(self):
        calls = []

        class Spy(_FailingRedis):
            def register_script(self, src):
                inner = super().register_script(src)
                def run(**kw):
                    calls.append(1)
                    return inner(**kw)
                return run

        breaker = CircuitBreaker("t", CircuitConfig(failure_threshold=1, recovery_timeout=60))
        limiter = RateLimiter(Spy(), breaker)
        limiter.check("k", 5, 60)  # fails, opens
        limiter.check("k", 5, 60)
        limiter.check("k", 5, 60)
        assert len(calls) == 1  # later requests did not even try Redis

    def test_half_open_allows_only_one_trial(self):
        breaker = CircuitBreaker("t", CircuitConfig(failure_threshold=1, recovery_timeout=0))
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert breaker.state == CircuitState.OPEN
        # first call after the timeout becomes the trial; a second concurrent one is rejected
        breaker.state = CircuitState.HALF_OPEN
        breaker.half_open_requests = 1
        with pytest.raises(Exception, match="OPEN"):
            breaker.call(lambda: "x")


class TestRealRedisAtomicity:
    def test_redis_counter_is_fixed_window_and_ttl_not_refreshed(self):
        from app.services.redis_client import get_redis_client

        client = get_redis_client()
        try:
            client.ping()
        except Exception:
            pytest.skip("Redis not running")
        limiter = RateLimiter(client)
        key = "rl:test:atomic"
        client.delete(key)
        for _ in range(3):
            limiter.check(key, 100, 60)
        ttl_first = client.ttl(key)
        import time
        time.sleep(1.1)
        limiter.check(key, 100, 60)
        assert client.ttl(key) < ttl_first  # TTL counts down; it is not re-armed per hit
        assert client.get(key) == "4"
        client.delete(key)

    def test_concurrent_requests_never_exceed_limit(self):
        from concurrent.futures import ThreadPoolExecutor

        from app.services.redis_client import get_redis_client

        client = get_redis_client()
        try:
            client.ping()
        except Exception:
            pytest.skip("Redis not running")
        limiter = RateLimiter(client)
        key = "rl:test:race"
        client.delete(key)
        with ThreadPoolExecutor(16) as pool:
            allowed = list(pool.map(lambda _: limiter.check(key, 25, 60).allowed, range(200)))
        assert sum(allowed) == 25  # exactly the limit, no read-then-write race
        client.delete(key)
