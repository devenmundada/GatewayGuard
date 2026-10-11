"""
Authentication middleware: validates the JWT on every non-public route.
"""
from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.auth import decode_token
from app.core.token_blacklist import is_access_token_revoked


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": detail},
        headers={"WWW-Authenticate": "Bearer"},
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticates requests and sets request.state.user_id / user_email / jti."""

    # Exact matches only. (startswith let "/healthz-anything" and "/metrics/x" skip auth.)
    PUBLIC_PATHS = frozenset(
        {
            "/",
            "/health",
            "/health/live",
            "/health/ready",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/auth/logout",
        }
    )

    async def dispatch(self, request: Request, call_next):
        # CORS preflight requests carry no credentials by design.
        if request.method == "OPTIONS" or request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _unauthorized("Missing or invalid authentication token")

        payload = decode_token(auth_header[7:].strip())
        if not payload or payload.get("type") != "access":
            return _unauthorized("Invalid or expired token")

        try:
            user_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError):
            return _unauthorized("Invalid or expired token")

        jti = payload.get("jti")
        if jti and await is_access_token_revoked(jti):
            return _unauthorized("Token has been revoked")

        request.state.user_id = user_id
        request.state.user_email = payload.get("email")
        request.state.jti = jti
        return await call_next(request)
