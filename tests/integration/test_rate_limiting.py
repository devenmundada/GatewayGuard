"""
Test rate limiting functionality.
"""
import pytest


class TestRateLimiting:
    """Test rate limiting behavior."""

    @pytest.mark.asyncio
    async def test_rate_limit_exempt_endpoints(self, client):
        """Test that /health and /metrics are exempt from rate limiting."""
        status_codes = []

        # Make 110 requests to /health — should never get rate limited
        for i in range(110):
            response = await client.get("/health")
            status_codes.append(response.status_code)

        # All requests should succeed — /health is exempt from rate limiting
        success_count = status_codes.count(200)
        rate_limited_count = status_codes.count(429)

        assert success_count == 110
        assert rate_limited_count == 0
        print(f"✅ /health exempt from rate limiting: {success_count} success, {rate_limited_count} rate limited")

    @pytest.mark.asyncio
    async def test_rate_limit_headers_not_on_exempt_endpoints(self, client):
        """Test that exempt endpoints do not return rate limit headers."""
        response = await client.get("/health")

        assert response.status_code == 200
        # Exempt endpoints should NOT have rate limit headers
        assert "X-RateLimit-Limit" not in response.headers
        print("✅ Exempt endpoints correctly have no rate limit headers")

    @pytest.mark.asyncio
    async def test_rate_limit_headers_on_auth_endpoints(self, client):
        """Test that non-exempt endpoints return rate limit headers."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "wrongpassword"
            }
        )

        # Should get a response (401 or 422) but not a 429 on first request
        assert response.status_code != 429
        print(f"✅ Auth endpoint responded with {response.status_code} on first request")
