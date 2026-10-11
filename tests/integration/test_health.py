"""Health endpoints must report real dependency state."""
from unittest.mock import AsyncMock, patch

import pytest


class TestHealth:
    @pytest.mark.asyncio
    async def test_ready_returns_503_when_database_down(self, client):
        with patch("app.api.health._check_database", new=AsyncMock(return_value="down")), \
             patch("app.api.health._check_redis", new=AsyncMock(return_value="ok")):
            response = await client.get("/health/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["checks"]["database"] == "down"

    @pytest.mark.asyncio
    async def test_ready_stays_200_when_only_redis_is_degraded(self, client):
        with patch("app.api.health._check_database", new=AsyncMock(return_value="ok")), \
             patch("app.api.health._check_redis", new=AsyncMock(return_value="degraded")):
            response = await client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["checks"]["redis"] == "degraded"

    @pytest.mark.asyncio
    async def test_liveness_ignores_database_outage(self, client):
        with patch("app.api.health._check_database", new=AsyncMock(return_value="down")):
            response = await client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    @pytest.mark.asyncio
    async def test_health_endpoints_are_not_rate_limited(self, client):
        with patch("app.api.health._check_database", new=AsyncMock(return_value="ok")), \
             patch("app.api.health._check_redis", new=AsyncMock(return_value="ok")):
            codes = [(await client.get("/health/ready")).status_code for _ in range(120)]

        assert codes.count(429) == 0
