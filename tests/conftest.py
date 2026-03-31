"""
Pytest configuration and fixtures.
"""
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import engine
from app.db.models import Base
from app.middleware.rate_limiter_middleware import RateLimiterMiddleware
from app.db import crud
from app.services.redis_client import get_redis_client

# Reset rate limiter between tests
@pytest.fixture(autouse=True)
def reset_rate_limit_memory():
    """Isolate tests: clear in-memory rate limit buckets and Redis keys."""
    # Clear memory store
    inst = RateLimiterMiddleware._active_instance
    if inst is not None:
        inst.rate_limiter.memory_store.clear()
    
    # Clear Redis rate limit keys
    try:
        redis_client = get_redis_client()
        if redis_client:
            keys = redis_client.keys("rl:*")
            if keys:
                redis_client.delete(*keys)
    except Exception as e:
        print(f"Warning: Could not clear Redis keys: {e}")
    
    # Reset auth in-memory stores
    crud.reset_memory_stores()
    
    yield
    
    # Cleanup after test
    if inst is not None:
        inst.rate_limiter.memory_store.clear()
    try:
        redis_client = get_redis_client()
        if redis_client:
            keys = redis_client.keys("rl:*")
            if keys:
                redis_client.delete(*keys)
    except Exception:
        pass
    crud.reset_memory_stores()

# Setup test database (skip if DB not available)
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Create tables before tests run (if DB is available)."""
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
        print("Warning: Could not drop test database tables")

@pytest_asyncio.fixture
async def client() -> AsyncGenerator:
    """Create test client for FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest_asyncio.fixture
def test_user():
    """Create test user data."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPassword123"
    }

@pytest_asyncio.fixture
async def auth_headers(client, test_user):
    """Get authentication headers for test user."""
    # Register user
    resp = await client.post("/api/v1/auth/register", json=test_user)
    if resp.status_code == 429:
        # If rate limited, wait and retry
        import asyncio
        await asyncio.sleep(1)
        resp = await client.post("/api/v1/auth/register", json=test_user)
    
    # Login
    response = await client.post("/api/v1/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"]
    })
    
    if response.status_code == 429:
        import asyncio
        await asyncio.sleep(1)
        response = await client.post("/api/v1/auth/login", json={
            "email": test_user["email"],
            "password": test_user["password"]
        })
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
