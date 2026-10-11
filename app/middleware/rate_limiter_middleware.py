"""
Rate limiting middleware.

Runs INSIDE AuthMiddleware (see main.py) so that request.state.user_id is already set
and logged-in users get their own, higher, per-user limit instead of sharing an IP
bucket.
"""
import asyncio
import logging

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.api.metrics import RATE_LIMITED
from app.core.rate_limiter import RateLimiter, RateLimitResult
from app.services.redis_client import get_redis_client
from app.utils.client_ip import get_client_ip

logger = logging.getLogger(__name__)

LIMITS = {
    "default": {"limit": 100, "window": 60},
    "auth": {"limit": 10, "window": 60},
    "authenticated": {"limit": 200, "window": 60},
}

EXEMPT_PREFIXES = ("/health", "/metrics")


_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """The process-wide limiter (one per worker; Redis is what is shared between workers)."""
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(get_redis_client())
    return _limiter


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = get_rate_limiter()
        logger.info("Rate limiter middleware initialized")

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)

        # Only the limiter's own logic is inside the try block; call_next must never be
        # reachable from the except branch or a failing app would be invoked twice.
        try:
            user_id = getattr(request.state, "user_id", None)
            if user_id:
                tier = "authenticated"
                key = f"rl:user:{user_id}"
            else:
                tier = "auth" if request.url.path.startswith("/api/v1/auth") else "default"
                key = f"rl:{tier}:ip:{get_client_ip(request)}"
            config = LIMITS[tier]
            # The Redis client is synchronous: run it in a thread so a slow Redis
            # cannot freeze the event loop for every other request.
            result: RateLimitResult = await asyncio.to_thread(
                self.rate_limiter.check, key, config["limit"], config["window"]
            )
        except Exception:
            logger.error("Rate limiter error, failing open", exc_info=True)
            return await call_next(request)

        if not result.allowed:
            RATE_LIMITED.labels(tier).inc()
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"Rate limit exceeded. Limit: {config['limit']} per "
                    f"{config['window']} seconds.",
                    "limit": config["limit"],
                    "remaining": 0,
                },
                headers={
                    "Retry-After": str(result.retry_after),
                    "X-RateLimit-Limit": str(config["limit"]),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(config["limit"])
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        return response
