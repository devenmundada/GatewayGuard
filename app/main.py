"""
GatewayGuard - FastAPI API gateway with authentication, rate limiting and observability.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.v1 import auth, tasks
from app.config import settings
from app.db.database import engine
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.correlation import CorrelationIDMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.metrics_middleware import MetricsMiddleware
from app.middleware.rate_limiter_middleware import RateLimiterMiddleware
from app.services.redis_client import close_redis_client
from app.utils.logging import setup_logging

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting GatewayGuard",
        extra={"environment": settings.ENVIRONMENT, "version": VERSION},
    )
    yield
    # Release pooled DB connections and the Redis socket on shutdown.
    await engine.dispose()
    close_redis_client()
    logger.info("GatewayGuard stopped")


app = FastAPI(
    title="GatewayGuard API Gateway",
    description="API gateway with JWT authentication, rate limiting and observability.",
    version=VERSION,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# Middleware order. Starlette wraps in REVERSE of registration: the LAST add_middleware
# call is the OUTERMOST layer, the first is closest to the route. A request travels:
#
#   CORS -> CorrelationID -> Logging -> Metrics -> Auth -> RateLimiter -> route
#
# Why this order:
#  - CORS outermost: even 401/429 responses carry CORS headers, and preflights are answered.
#  - CorrelationID before Logging/Metrics: every log line and every rejected request
#    (401, 429) has a request id, and the id is on the response.
#  - Logging/Metrics outside Auth and RateLimiter: rejected requests are still logged
#    and counted (a 429 spike must show up in Grafana).
#  - Auth before RateLimiter: the limiter needs request.state.user_id to apply the
#    per-user limit instead of the per-IP one.
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
)

app.include_router(health_router, prefix="", tags=["Health"])
app.include_router(metrics_router, prefix="", tags=["Metrics"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])


@app.exception_handler(SQLAlchemyError)
@app.exception_handler(OSError)  # asyncpg raises ConnectionRefusedError etc. unwrapped
@app.exception_handler(asyncio.TimeoutError)
async def dependency_unavailable_handler(request: Request, exc: Exception):
    """PostgreSQL unreachable/slow: say so (503, retryable) instead of a fake 401/500."""
    logger.error("Database unavailable: %s", exc, extra={"path": request.url.path})
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Service temporarily unavailable"},
        headers={"Retry-After": "5"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception", extra={"path": request.url.path})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "GatewayGuard API Gateway", "status": "operational"}
