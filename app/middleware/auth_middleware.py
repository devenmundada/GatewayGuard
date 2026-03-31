"""
Authentication middleware to validate JWT tokens.
"""
from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.auth import decode_token

class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to authenticate requests."""
    
    # Public paths that don't require authentication
    PUBLIC_PATHS = [
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
    ]
    
    async def dispatch(self, request: Request, call_next):
        # Check if path is public
        path = request.url.path
        if any(path.startswith(public_path) for public_path in self.PUBLIC_PATHS):
            return await call_next(request)
        
        # Check for token in Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid authentication token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header.split(" ")[1]
        payload = decode_token(token)

        if not payload or payload.get("type") != "access":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Add user info to request state
        request.state.user_id = int(payload.get("sub"))
        request.state.user_email = payload.get("email")
        
        return await call_next(request)
