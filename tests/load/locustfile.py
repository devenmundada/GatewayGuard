from locust import HttpUser, task, between

class GatewayUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def health_check(self):
        self.client.get("/health")
    
    @task(2)
    def register_and_login(self):
        # Register
        email = f"test_{self.runner.host}_{self.id}.example.com"
        self.client.post("/api/v1/auth/register", json={
            "email": email,
            "username": f"user_{self.id}",
            "password": "Test123"
        })
        
        # Login
        self.client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "Test123"
        })
    
    @task(1)
    def protected_endpoint(self):
        # This would need a token - for now, just health
        self.client.get("/health")
