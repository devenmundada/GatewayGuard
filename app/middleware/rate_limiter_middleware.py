"""
Rate limiting middleware with Redis integration.
"""
import logging
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.rate_limiter import RateLimiter
from app.services.redis_client import get_redis_client
from typing import Optional

logger = logging.getLogger(__name__)

LIMITS = {
    "default": {"limit": 100, "window": 60},
    "auth": {"limit": 10, "window": 60},
    "authenticated": {"limit": 200, "window": 60},
}

class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Holds the last constructed instance so tests can reset in-memory counters."""
    _active_instance: Optional["RateLimiterMiddleware"] = None
    
    def __init__(self, app):
        super().__init__(app)
        redis_client = get_redis_client()
        self.rate_limiter = RateLimiter(redis_client)
        RateLimiterMiddleware._active_instance = self
        logger.info("Rate limiter middleware initialized")
    
    async def dispatch(self, request: Request, call_next):
        try:
            user_id = getattr(request.state, "user_id", None)
            
            if user_id:
                key = f"rl:user:{user_id}"
                limit_config = LIMITS["authenticated"]
            else:
                client_ip = request.client.host if request.client else "unknown"
                key = f"rl:ip:{client_ip}"
                if request.url.path.startswith("/api/v1/auth"):
                    limit_config = LIMITS["auth"]
                else:
                    limit_config = LIMITS["default"]
            
            allowed, remaining = self.rate_limiter.check_rate_limit(
                key,
                limit=limit_config["limit"],
                window=limit_config["window"]
            )
            
            if not allowed:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": f"Rate limit exceeded. Limit: {limit_config['limit']} per {limit_config['window']} seconds.",
                        "limit": limit_config["limit"],
                        "remaining": 0
                    }
                )
            
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit_config["limit"])
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}", exc_info=True)
            # Fail open - allow request
            return await call_next(request)
