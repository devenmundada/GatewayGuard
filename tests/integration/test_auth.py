"""
Test authentication functionality.
"""
import pytest

class TestAuthentication:
    """Test authentication flows."""
    
    @pytest.mark.asyncio
    async def test_register_user(self, client, test_user):
        """Test user registration."""
        response = await client.post("/api/v1/auth/register", json=test_user)
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == test_user["email"]
        assert data["username"] == test_user["username"]
        assert "id" in data
        print(f"✅ User registered: {data['email']}")
    
    @pytest.mark.asyncio
    async def test_duplicate_registration_fails(self, client, test_user):
        """Test duplicate registration fails."""
        # First registration
        await client.post("/api/v1/auth/register", json=test_user)
        
        # Second registration with same email
        response = await client.post("/api/v1/auth/register", json=test_user)
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
        print("✅ Duplicate registration correctly blocked")
    
    @pytest.mark.asyncio
    async def test_login_success(self, client, test_user):
        """Test successful login returns tokens."""
        # Register user
        await client.post("/api/v1/auth/register", json=test_user)
        
        # Login
        response = await client.post("/api/v1/auth/login", json={
            "email": test_user["email"],
            "password": test_user["password"]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        print("✅ Login successful, tokens returned")
    
    @pytest.mark.asyncio
    async def test_login_wrong_password_fails(self, client, test_user):
        """Test wrong password returns 401."""
        # Register user
        await client.post("/api/v1/auth/register", json=test_user)
        
        # Login with wrong password
        response = await client.post("/api/v1/auth/login", json={
            "email": test_user["email"],
            "password": "WrongPassword"
        })
        
        assert response.status_code == 401
        print("✅ Wrong password correctly rejected")
    
    @pytest.mark.asyncio
    async def test_protected_route_without_token_fails(self, client):
        """Test protected route without token returns 401."""
        response = await client.get("/api/v1/tasks")
        
        assert response.status_code == 401
        assert "missing" in response.json()["detail"].lower()
        print("✅ Protected route without token correctly blocked")

    @pytest.mark.asyncio
    async def test_protected_route_with_valid_token_succeeds(self, client, test_user, auth_headers):
        """Test protected route with valid token succeeds."""
        response = await client.get("/api/v1/tasks", headers=auth_headers)
        
        # Tasks endpoint should return empty list for new user
        assert response.status_code == 200
        assert response.json() == []
        print("✅ Protected route with valid token works")
    
    @pytest.mark.asyncio
    async def test_invalid_token_fails(self, client):
        """Test invalid token returns 401."""
        response = await client.get(
            "/api/v1/tasks",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        
        assert response.status_code == 401
        print("✅ Invalid token correctly rejected")
