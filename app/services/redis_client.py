"""
Redis client with connection handling.
"""
import logging
import redis
from app.config import settings

logger = logging.getLogger(__name__)

_redis_client = None

def get_redis_client():
    """Get Redis client (singleton)."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True
            )
            _redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Rate limiting will use in-memory fallback.")
            _redis_client = None
    return _redis_client
