"""Middleware order, per-user limits, request ids, metrics."""
from app.middleware.rate_limiter_middleware import LIMITS


class TestMiddlewareOrder:
    async def test_rejected_requests_still_get_request_id(self, client):
        # 401 produced by AuthMiddleware must still pass back through CorrelationID.
        response = await client.get("/api/v1/tasks")
        assert response.status_code == 401
        assert "x-request-id" in response.headers

    async def test_incoming_request_id_is_echoed(self, client):
        response = await client.get("/", headers={"X-Request-ID": "abc-123"})
        assert response.headers["x-request-id"] == "abc-123"

    async def test_429_responses_get_request_id_and_retry_after(self, client):
        last = None
        for _ in range(LIMITS["auth"]["limit"] + 1):
            last = await client.post(
                "/api/v1/auth/login", json={"email": "a@example.com", "password": "x"}
            )
        assert last.status_code == 429
        assert "x-request-id" in last.headers
        assert int(last.headers["retry-after"]) >= 1

    async def test_authenticated_user_gets_per_user_limit(self, client, auth_headers):
        response = await client.get("/api/v1/tasks", headers=auth_headers)
        assert response.headers["x-ratelimit-limit"] == str(LIMITS["authenticated"]["limit"])

    async def test_anonymous_gets_ip_limit(self, client):
        response = await client.get("/")
        assert response.headers["x-ratelimit-limit"] == str(LIMITS["default"]["limit"])

    async def test_cors_headers_present_on_401(self, client):
        response = await client.get(
            "/api/v1/tasks", headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 401
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


class TestMetrics:
    async def test_requests_are_counted_with_route_template(self, client, auth_headers):
        created = (
            await client.post("/api/v1/tasks", json={"title": "m"}, headers=auth_headers)
        ).json()
        await client.get(f"/api/v1/tasks/{created['id']}", headers=auth_headers)
        await client.get("/no/such/path/12345", headers=auth_headers)

        body = (await client.get("/metrics")).text
        assert 'endpoint="/api/v1/tasks/{task_id}"' in body
        assert f"/api/v1/tasks/{created['id']}" not in body  # no per-id label explosion
        assert 'endpoint="unmatched"' in body
        assert "http_request_duration_seconds_bucket" in body
        assert 'status="404"' in body

    async def test_rate_limited_requests_are_counted(self, client):
        for _ in range(LIMITS["auth"]["limit"] + 2):
            await client.post(
                "/api/v1/auth/login", json={"email": "a@example.com", "password": "x"}
            )
        body = (await client.get("/metrics")).text
        assert 'http_rate_limited_total{tier="auth"}' in body
