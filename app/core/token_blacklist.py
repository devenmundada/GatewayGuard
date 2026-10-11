"""
Access-token revocation list.

Access tokens are stateless JWTs, so "logout" cannot invalidate them by itself. On
logout we store the token's `jti` in Redis until the token would have expired anyway;
AuthMiddleware rejects any token whose jti is listed.

Fail-open on purpose: if Redis is down we cannot check, and refusing every request
because the revocation list is unreachable would turn a Redis outage into a total
outage. Tokens live only 15 minutes. The trade-off is logged.
"""
import asyncio
import logging

from app.services.redis_client import get_redis_client

logger = logging.getLogger(__name__)

_PREFIX = "revoked:jti:"


def _revoke_sync(jti: str, ttl_seconds: int) -> bool:
    client = get_redis_client()
    if client is None or ttl_seconds <= 0:
        return False
    client.set(f"{_PREFIX}{jti}", "1", ex=ttl_seconds)
    return True


def _is_revoked_sync(jti: str) -> bool:
    client = get_redis_client()
    if client is None:
        return False
    return bool(client.exists(f"{_PREFIX}{jti}"))


async def revoke_access_token(jti: str, ttl_seconds: int) -> bool:
    try:
        return await asyncio.to_thread(_revoke_sync, jti, ttl_seconds)
    except Exception as exc:
        logger.error("Could not record revoked token (Redis down?): %s", exc)
        return False


async def is_access_token_revoked(jti: str) -> bool:
    try:
        return await asyncio.to_thread(_is_revoked_sync, jti)
    except Exception as exc:
        logger.warning("Revocation check skipped (Redis down?): %s", exc)
        return False
