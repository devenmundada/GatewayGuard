"""Authentication flows against real PostgreSQL and Redis."""


async def _register_and_login(client, user):
    await client.post("/api/v1/auth/register", json=user)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200
    return resp.json()


class TestAuthentication:
    async def test_register_user(self, client, test_user):
        response = await client.post("/api/v1/auth/register", json=test_user)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == test_user["email"]
        assert data["username"] == test_user["username"]
        assert "id" in data
        assert "password" not in data and "hashed_password" not in data

    async def test_duplicate_registration_fails(self, client, test_user):
        await client.post("/api/v1/auth/register", json=test_user)
        response = await client.post("/api/v1/auth/register", json=test_user)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    async def test_duplicate_message_does_not_reveal_which_field(self, client, test_user):
        await client.post("/api/v1/auth/register", json=test_user)
        same_email = dict(test_user, username="different")
        same_username = dict(test_user, email="different@example.com")
        a = await client.post("/api/v1/auth/register", json=same_email)
        b = await client.post("/api/v1/auth/register", json=same_username)
        assert a.status_code == b.status_code == 400
        assert a.json() == b.json()

    async def test_short_password_rejected(self, client, test_user):
        response = await client.post(
            "/api/v1/auth/register", json=dict(test_user, password="short1")
        )
        assert response.status_code == 422

    async def test_email_is_case_insensitive(self, client, test_user):
        await client.post("/api/v1/auth/register", json=test_user)
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"].upper(), "password": test_user["password"]},
        )
        assert response.status_code == 200

    async def test_login_success(self, client, test_user):
        data = await _register_and_login(client, test_user)
        assert "access_token" in data and "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password_fails(self, client, test_user):
        await client.post("/api/v1/auth/register", json=test_user)
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": "WrongPassword"},
        )
        assert response.status_code == 401

    async def test_login_unknown_user_gets_same_error(self, client, test_user):
        await client.post("/api/v1/auth/register", json=test_user)
        wrong = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user["email"], "password": "WrongPassword"},
        )
        unknown = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "WrongPassword"},
        )
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json()

    async def test_protected_route_without_token_fails(self, client):
        response = await client.get("/api/v1/tasks")
        assert response.status_code == 401
        assert "missing" in response.json()["detail"].lower()

    async def test_protected_route_with_valid_token_succeeds(self, client, auth_headers):
        response = await client.get("/api/v1/tasks", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    async def test_invalid_token_fails(self, client):
        response = await client.get(
            "/api/v1/tasks", headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401

    async def test_refresh_token_cannot_be_used_as_access_token(self, client, test_user):
        tokens = await _register_and_login(client, test_user)
        response = await client.get(
            "/api/v1/tasks",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        )
        assert response.status_code == 401

    async def test_public_path_match_is_exact(self, client):
        # Used to be a startswith() match, so anything beginning with /health skipped auth.
        response = await client.get("/health-anything-else")
        assert response.status_code == 401
        response = await client.get("/metrics/secret")
        assert response.status_code == 401


class TestRefreshAndLogout:
    async def test_refresh_rotates_token(self, client, test_user):
        tokens = await _register_and_login(client, test_user)
        first = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert first.status_code == 200
        assert first.json()["refresh_token"] != tokens["refresh_token"]

        # Single use: the old refresh token no longer works.
        replay = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert replay.status_code == 401

    async def test_refresh_token_not_accepted_in_query_string(self, client, test_user):
        tokens = await _register_and_login(client, test_user)
        response = await client.post(
            f"/api/v1/auth/refresh?refresh_token={tokens['refresh_token']}"
        )
        assert response.status_code == 422

    async def test_refresh_with_access_token_fails(self, client, test_user):
        tokens = await _register_and_login(client, test_user)
        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
        )
        assert response.status_code == 401

    async def test_logout_revokes_refresh_token(self, client, test_user):
        tokens = await _register_and_login(client, test_user)
        out = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
        )
        assert out.status_code == 200
        again = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert again.status_code == 401

    async def test_logout_revokes_access_token_immediately(self, client, test_user):
        tokens = await _register_and_login(client, test_user)
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        assert (await client.get("/api/v1/tasks", headers=headers)).status_code == 200

        await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers=headers,
        )
        after = await client.get("/api/v1/tasks", headers=headers)
        assert after.status_code == 401
        assert "revoked" in after.json()["detail"].lower()

    async def test_refresh_tokens_are_stored_hashed(self, client, test_user):
        from sqlalchemy import text

        from app.db.database import engine

        tokens = await _register_and_login(client, test_user)
        async with engine.connect() as conn:
            rows = (await conn.execute(text("SELECT token_hash FROM refresh_tokens"))).all()
        assert len(rows) == 1
        assert rows[0][0] != tokens["refresh_token"]
        assert len(rows[0][0]) == 64
