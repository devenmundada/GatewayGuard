"""
Fixed-window rate limiting: Redis (shared by all workers and pods) with a per-process
in-memory fallback.

Redis path: one atomic Lua script does INCR and, only for the first hit of a window,
EXPIRE. Atomic means two workers can never both read "99" and both let request 100
through, and the expiry is set once so the window really is fixed (the old code
re-armed the TTL on every hit, which meant a steady trickle never reset the counter).

Redis calls run under a circuit breaker: when Redis is down, requests fall back to
memory immediately instead of each waiting out a socket timeout, and Redis is retried
automatically after the recovery timeout.

Honest limitation: the memory fallback is per process, so with N gunicorn workers the
effective limit while Redis is down is up to N times higher. It keeps the gateway
protected, not precise.
"""
import logging
import threading
import time
from typing import NamedTuple

import redis

from app.core.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitOpenError

logger = logging.getLogger(__name__)

# KEYS[1] = counter key, ARGV[1] = window seconds. Returns {count, ttl_seconds}.
_FIXED_WINDOW_LUA = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
  ttl = tonumber(ARGV[1])
end
return {count, ttl}
"""


class RateLimitResult(NamedTuple):
    allowed: bool
    remaining: int
    retry_after: int  # seconds until the window resets


class RateLimiter:
    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        breaker: CircuitBreaker | None = None,
    ):
        self.redis = redis_client
        self.breaker = breaker or CircuitBreaker(
            "redis-rate-limiter", CircuitConfig(failure_threshold=3, recovery_timeout=10)
        )
        # key -> (window_start, count)
        self.memory_store: dict[str, tuple[float, int]] = {}
        self._memory_lock = threading.Lock()
        self._script = redis_client.register_script(_FIXED_WINDOW_LUA) if redis_client else None

    @property
    def redis_available(self) -> bool:
        """True while Redis is being used (breaker not OPEN)."""
        return self.redis is not None and self.breaker.state.value != "open"

    def _memory_check(self, key: str, limit: int, window: int) -> RateLimitResult:
        now = time.time()
        with self._memory_lock:
            start, count = self.memory_store.get(key, (now, 0))
            if now - start >= window:
                start, count = now, 0
            count += 1
            self.memory_store[key] = (start, count)
            if len(self.memory_store) > 10_000:  # bound memory under key churn
                self._evict_expired(now, window)
        retry_after = max(1, int(start + window - now))
        if count > limit:
            return RateLimitResult(False, 0, retry_after)
        return RateLimitResult(True, limit - count, retry_after)

    def _evict_expired(self, now: float, window: int) -> None:
        for k in [k for k, (s, _) in self.memory_store.items() if now - s >= window]:
            del self.memory_store[k]

    def _redis_check(self, key: str, limit: int, window: int) -> RateLimitResult:
        count, ttl = self._script(keys=[key], args=[window])
        count, ttl = int(count), max(int(ttl), 1)
        if count > limit:
            return RateLimitResult(False, 0, ttl)
        return RateLimitResult(True, limit - count, ttl)

    def check(self, key: str, limit: int, window: int) -> RateLimitResult:
        """Count this request against `key`. Never raises: degrades to memory."""
        if self.redis is not None:
            try:
                return self.breaker.call(self._redis_check, key, limit, window)
            except CircuitOpenError:
                pass  # Redis known to be down; skip it without waiting for a timeout
            except Exception as exc:
                logger.error("Redis rate limit check failed (%s); using memory fallback", exc)
        return self._memory_check(key, limit, window)

    def check_rate_limit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Tuple form of check(): (allowed, remaining)."""
        result = self.check(key, limit, window)
        return result.allowed, result.remaining
