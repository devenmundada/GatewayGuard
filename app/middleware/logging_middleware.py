"""
Middleware to log requests with correlation ID.
"""

import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming requests and their responses."""
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        start_time = time.time()

        # Log request
        logger.info(
            "Request started",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None,
            }
        )

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Log response
            logger.info(
                "Request completed",
                extra={
                    "correlation_id": correlation_id,
                    "status_code": response.status_code,
                    "duration_ms": round(process_time * 1000, 2),
                }
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.exception(
                "Request failed",
                extra={
                    "correlation_id": correlation_id,
                    "duration_ms": round(process_time * 1000, 2),
                    "error": str(e),
                }
            )
            raise