"""
GatewayGuard - Main FastAPI Application
Production-grade API Gateway with authentication, rate limiting, and observability.
"""

import logging
from contextlib import asynccontextmanager

from app.middleware.rate_limiter_middleware import RateLimiterMiddleware


from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.v1 import auth, tasks
from app.config import settings
from app.middleware.correlation import CorrelationIDMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.auth_middleware import AuthMiddleware
from app.utils.logging import setup_logging

# Configure structured logging
setup_logging(settings.LOG_LEVEL)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting GatewayGuard API Gateway", extra={
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
    })
    # Initialize connections (DB, Redis) will be added later
    yield
    # Shutdown
    logger.info("Shutting down GatewayGuard API Gateway")


# Create FastAPI instance
app = FastAPI(
    title="GatewayGuard API Gateway",
    description="Production-grade API Gateway with authentication, rate limiting, and observability.",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# CORS middleware (must be first to handle preflight)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware order:
# CorrelationIDMiddleware -> LoggingMiddleware -> AuthMiddleware -> RateLimiterMiddleware
app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthMiddleware)  # Add auth middleware
app.add_middleware(RateLimiterMiddleware)

# Include routers
app.include_router(health_router, prefix="", tags=["Health"])
app.include_router(metrics_router, prefix="", tags=["Metrics"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])


# Exception handlers
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler to log unexpected errors."""
    logger.exception("Unhandled exception", extra={"path": request.url.path})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Root endpoint (optional)
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "GatewayGuard API Gateway", "status": "operational"}