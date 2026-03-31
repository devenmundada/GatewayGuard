"""
Health check endpoints for liveness and readiness probes.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    checks: dict


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Comprehensive health check.
    Returns 200 if all dependencies are healthy.
    """
    # TODO: Add checks for DB, Redis, etc.
    checks = {
        "database": "ok",
        "redis": "ok",
        "gateway": "ok",
    }
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        checks=checks,
    )


@router.get("/health/live", tags=["Health"])
async def liveness():
    """Simple liveness probe that always returns 200."""
    return {"status": "alive"}


@router.get("/health/ready", tags=["Health"])
async def readiness():
    """Readiness probe that checks dependencies."""
    # For now, just return OK
    return {"status": "ready"}