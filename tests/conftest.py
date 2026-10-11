"""
Pytest configuration and fixtures.

Tests need a real PostgreSQL (tables created by `alembic upgrade head`) and, for the
Redis-backed tests, a real Redis. There is no in-memory fake database any more: a test
that passes must have actually exercised PostgreSQL.
"""
import os
import sys
from pathlib import Path

# Must be set before the app is imported: selects the connection-pool-free engine that
# works with pytest-asyncio's one-event-loop-per-test.
os.environ.setdefault("ENVIRONMENT", "testing")

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.circuit_breaker import CircuitState  # noqa: E402
from app.db.database import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.rate_limiter_middleware import get_rate_limiter  # noqa: E402


@pytest.fixture(autouse=True)
async def clean_state():
    """Every test starts with empty tables and fresh rate-limit counters."""
    limiter = get_rate_limiter()
    limiter.memory_store.clear()
    limiter.breaker.state = CircuitState.CLOSED
    limiter.breaker.failure_count = 0
    if limiter.redis is not None:
        try:
            for pattern in ("rl:*", "revoked:jti:*"):
                for key in limiter.redis.scan_iter(pattern):
                    limiter.redis.delete(key)
        except Exception:
            pass  # Redis not running: the limiter falls back to memory

    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE TABLE tasks, refresh_tokens, users RESTART IDENTITY CASCADE")
        )
    yield


@pytest.fixture
async def client():
    """HTTP client wired straight to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def test_user():
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPassword123",
    }


@pytest.fixture
def other_user():
    return {
        "email": "other@example.com",
        "username": "otheruser",
        "password": "OtherPassword123",
    }


async def _login_headers(client, user) -> dict:
    await client.post("/api/v1/auth/register", json=user)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def auth_headers(client, test_user):
    return await _login_headers(client, test_user)


@pytest.fixture
async def other_auth_headers(client, other_user):
    return await _login_headers(client, other_user)
