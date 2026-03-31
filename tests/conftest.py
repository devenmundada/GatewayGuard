"""
Pytest configuration and fixtures.
"""
import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import engine
from app.db.models import Base
from app.middleware.rate_limiter_middleware import RateLimiterMiddleware
from app.db import crud

# Reset rate limiter between tests
@pytest.fixture(autouse=True)
def reset_rate_limit_memory():
    """Isolate tests: clear in-memory rate limit buckets."""
    inst = RateLimiterMiddleware._active_instance
    if inst is not None:
        inst.rate_limiter.memory_store.clear()
    
    # Reset auth in-memory stores
    crud.reset_memory_stores()
    
    yield
    
    if inst is not None:
        inst.rate_limiter.memory_store.clear()
    crud.reset_memory_stores()


# Session-scoped event loop for database setup
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for entire test session."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Database setup - runs once per session
@pytest.fixture(scope="session")
async def setup_database():
    """Create tables before tests run."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Using real PostgreSQL for tests")
    except Exception as e:
        print(f"⚠️ PostgreSQL not available ({e}), using in-memory fallback")
    yield
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    except Exception:
        pass


# Test client - function scoped
@pytest.fixture
async def client():
    """Create test client for FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=tra, base_url="http://test") as client:
        yield client


# Test user data
@pytest.fixture
def test_user():
    """Create test user data."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPassword123"
    }


# Auth headers - function scoped
@pytest.fixture
async def auth_headers(client, test_user):
    """Get authentication headers for test user."""
    # Register user
    resp = await client.post("/api/v1/auth/register", json=test_user)
    if resp.status_code == 429:
        import asyncio
        await asyncio.sleep(0.1)
        resp = await client.post("/api/v1/auth/register", json=test_user)
    
    # Login
    response = await client.post("/api/v1/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"]
    })
    
    if response.status_code == 429:
        import asyncio
        await asyncio.sleep(0.1)
        response = await client.post("/api/v1/auth/login", json={
            "email": test_user["email"],
            "password": test_user["password"]
        })
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
