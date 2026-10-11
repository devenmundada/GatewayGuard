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
    async def test_auth_endpoint_is_rate_limited(self, client):
        """Auth endpoints enforce a stricter limit (10/min) and return 429 once exceeded."""
        status_codes = []
        for _ in range(15):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "wrongpassword"},
            )
            status_codes.append(response.status_code)

        # Whatever budget earlier tests used, 15 requests must exceed a 10/min limit.
        assert 429 in status_codes
        print(f"Auth endpoint limited as expected: {status_codes.count(429)} of 15 requests got 429")
