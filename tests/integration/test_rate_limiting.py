"""
Test rate limiting functionality.
"""
import pytest


class TestRateLimiting:
    """Test rate limiting behavior."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_public_endpoint(self, client):
        """Test that public endpoints are rate limited."""
        status_codes = []
        
        # Make 105 requests to exceed 100 limit
        for i in range(105):
            response = await client.get("/health")
            status_codes.append(response.status_code)
        
        # Count 200 and 429 responses
        # `/api/v1/auth/register` returns `201 Created` on success.
        success_count = sum(1 for code in status_codes if code in (200, 201))
        rate_limited_count = status_codes.count(429)
        
        # First 100 should succeed, next 5 should be rate limited
        assert success_count >= 100
        assert rate_limited_count >= 5
        print(f"✅ Rate limiting works: {success_count} success, {rate_limited_count} rate limited")
    
    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, client):
        """Test that rate limit headers are returned."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

    @pytest.mark.asyncio
    async def test_different_limits_for_auth_endpoints(self, client):
        """Test that auth endpoints have stricter limits."""
        status_codes = []
        
        # Make 15 requests to auth endpoint (limit should be 10)
        for i in range(15):
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"test{i}@example.com",
                    "username": f"testuser{i}",
                    "password": "Test123"
                }
            )
            status_codes.append(response.status_code)
        
        # `/api/v1/auth/register` returns `201 Created` on success.
        success_count = sum(1 for code in status_codes if code in (200, 201))
        rate_limited_count = status_codes.count(429)
        
        # Auth endpoints have stricter limit (10 per minute)
        assert success_count >= 10
        assert rate_limited_count >= 4
        print(f"✅ Auth endpoints have stricter limits: {success_count} success, {rate_limited_count} rate limited")
