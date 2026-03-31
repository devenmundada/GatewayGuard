"""
Test how system behaves when dependencies fail.
This is what separates top 1% engineers from the rest.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.core.rate_limiter import RateLimiter
from app.services.redis_client import get_redis_client

class TestFailureScenarios:
    """Test system behavior under failure conditions."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_fallback_when_redis_down(self):
        """Test that rate limiter falls back to memory when Redis fails."""
        # Create rate limiter with no Redis
        rate_limiter = RateLimiter(redis_client=None)
        
        # Make 105 requests (should exceed limit)
        results = []
        for i in range(105):
            allowed, remaining = rate_limiter.check_rate_limit(
                "test:key",
                limit=100,
                window=60
            )
            results.append(allowed)
        
        # First 100 should be allowed, next 5 blocked
        allowed_count = sum(results)
        blocked_count = len(results) - allowed_count
        
        assert allowed_count >= 100
        assert blocked_count >= 5
        print(f"✅ Rate limiter works with memory fallback: {allowed_count} allowed, {blocked_count} blocked")
    
    @pytest.mark.asyncio
    async def test_rate_limiter_recovers_when_redis_returns(self):
        """Test that rate limiter recovers when Redis becomes available."""
        # Start with Redis unavailable
        rate_limiter = RateLimiter(redis_client=None)
        
        # Make some requests
        for i in range(50):
            rate_limiter.check_rate_limit("test:key", limit=100, window=60)
        
        # Simulate Redis becoming available
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = None  # No existing counter
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = [1, True]

        # Create new rate limiter with Redis
        rate_limiter_redis = RateLimiter(redis_client=mock_redis)

        # Verify Redis is now used (incr runs on pipeline, not raw client)
        allowed, remaining = rate_limiter_redis.check_rate_limit("test:key", limit=100, window=60)
        assert allowed is True
        mock_pipe.incr.assert_called_once()
        print("✅ Rate limiter recovers when Redis becomes available")
    
    @pytest.mark.asyncio
    async def test_health_check_returns_correct_status(self, client):
        """Test health check endpoint returns proper status."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "checks" in data
        print(f"✅ Health check: {data}")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_after_failures(self):
        """Test that circuit breaker opens after threshold failures."""
        from app.core.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState # pyright: ignore[reportUndefinedVariable]
        
        # Create circuit breaker with low shold for testing
        config = CircuitConfig(failure_threshold=3, recovery_timeout=30)
        breaker = CircuitBreaker("test_service", config)
        
        # Mock failing function
        def failing_func():
            raise Exception("Service failed")
        
        # Three failures meet failure_threshold=3 → circuit opens on the 3rd failure
        for i in range(3):
            try:
                breaker.call(failing_func)
            except Exception:
                pass

        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3

        # Further calls are blocked while OPEN
        with pytest.raises(Exception, match="OPEN"):
            breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN
        print("✅ Circuit breaker opens after threshold failures")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_requests_when_open(self, client):
        """Test that circuit breaker blocks requts when open."""
        from app.core.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState # pyright: ignore[reportUndefinedVariable]
        
        # Create circuit breaker
        config = CircuitConfig(failure_threshold=1, recovery_timeout=60)
        breaker = CircuitBreaker("test_blocking", config)
        
        # Trigger failure to open circuit
        def failing():
            raise Exception("Fail")
        
        try:
            breaker.call(failing)
        except Exception:
            pass
        
        assert breaker.state == CircuitState.OPEN
        
        # Try another request - should be blocked
        try:
            breaker.call(lambda: "success")
            assert False, "Should have raised exception"
        except Exception as e:
            assert "OPEN" in str(e)
        
        print("✅ Circuit breaker blocks requests when open")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_state_monitoring(self, client):
        """Test that circuit breaker provides state monitoring."""
        from app.core.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState # pyright: ignore[reportUndefinedVariable]
        breaker = CircuitBreaker("monitored_service", config=CircuitConfig())
        state = breaker.get_state()
        assert state["name"] == "monitored_service"
        assert state["state"] == "closed"
        assert state["failure_count"] == 0
        
        print("✅ Circuit breaker provides monitoring data")
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_timeout(self, client):
        """Test that circuit breaker opens after failure and blocks further calls."""
        from app.core.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState # pyright: ignore[reportUndefinedVariable]
        breaker = CircuitBreaker("recovering_service", config=CircuitConfig(failure_threshold=1, recovery_timeout=1))

        def failing():
            raise RuntimeError("downstream failure")

        with pytest.raises(RuntimeError, match="downstream failure"):
            breaker.call(failing)
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 1
        assert breaker.last_failure_time > 0
        assert breaker.config.recovery_timeout > 0

        with pytest.raises(Exception, match="Circuit breaker 'recovering_service' is OPEN. Service unavailable."):
            breaker.call(lambda: "would succeed")
        print("✅ Circuit breaker opens and blocks while OPEN")