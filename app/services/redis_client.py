"""
Redis client (lazy, shared per process).

redis-py connects on first use, so creating the client never fails and never blocks
startup. Whether Redis is currently reachable is decided per call (and tracked by the
circuit breaker in the rate limiter), not once at import time.
"""
import logging

import redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis | None:
    """Return the process-wide Redis client, or None if the URL is invalid."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
        except Exception as exc:
            logger.error("Invalid REDIS_URL, rate limiting will use memory: %s", exc)
            return None
    return _redis_client


def close_redis_client() -> None:
    """Close the shared client (called on application shutdown)."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
        finally:
            _redis_client = None
