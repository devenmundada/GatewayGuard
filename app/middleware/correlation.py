"""
Middleware to inject and propagate correlation IDs.
"""

import uuid
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

CORRELATION_ID_HEADER = "X-Request-ID"


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Adds a correlation ID to each request and stores it in context."""
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Get correlation ID from header or generate a new one
        correlation_id = request.headers.get(CORRELATION_ID_HEADER)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in request state for later use
        request.state.correlation_id = correlation_id

        # Add to response headers
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response