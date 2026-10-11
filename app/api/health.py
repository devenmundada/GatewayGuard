"""
Health check endpoints for liveness and readiness probes.

- /health/live  : is the process alive? (no dependencies, never fails on a DB outage)
- /health/ready : can we serve traffic? (database required, Redis optional)
- /health       : same report as /health/ready, for humans and the aggregator
"""
import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.db.database import engine
from app.services.redis_client import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter()

CHECK_TIMEOUT_SECONDS = 2


class HealthResponse(BaseModel):
    status: str
    version: str
    checks: dict


async def _check_database() -> str:
    """Run SELECT 1 against PostgreSQL. 'ok' or 'down'."""
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        return "down"


def _ping_redis() -> bool:
    """Blocking Redis ping; runs in a worker thread."""
    client = get_redis_client()
    if client is None:
        return False
    try:
        client.ping()
        return True
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        return False


async def _check_redis() -> str:
    """'ok' or 'degraded' (the rate limiter can fall back to memory)."""
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS + 1):
            ok = await asyncio.to_thread(_ping_redis)
        return "ok" if ok else "degraded"
    except Exception:
        return "degraded"


async def _report() -> JSONResponse:
    database, redis_status = await asyncio.gather(_check_database(), _check_redis())
    ready = database == "ok"
    body = HealthResponse(
        status="healthy" if ready else "unhealthy",
        version="1.0.0",
        checks={"database": database, "redis": redis_status, "gateway": "ok"},
    )
    return JSONResponse(status_code=200 if ready else 503, content=body.model_dump())


@router.get("/health", tags=["Health"])
async def health_check():
    """Full dependency report. 503 if the database is down."""
    return await _report()


@router.get("/health/live", tags=["Health"])
async def liveness():
    """Simple liveness probe that always returns 200."""
    return {"status": "alive"}


@router.get("/health/ready", tags=["Health"])
async def readiness():
    """Readiness probe: 200 only if the database is reachable."""
    return await _report()
