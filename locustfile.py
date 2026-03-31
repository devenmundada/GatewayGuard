"""
Load testing for GatewayGuard API Gateway.
Tests performance under 50-100 concurrent users.
"""
from locust import HttpUser, task, between, events
import random
import string

class GatewayGuardUser(HttpUser):
    """
    Simulates a real user interacting with the API gateway.
    """
    wait_time = between(1, 3)  # Think time between requests
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_token = None
        self.refresh_token = None
        self.user_email = None
    
    def on_start(self):
        """Called when a user starts - register and login."""
        # Generate unique user
        self.user_id = random.randint(10000, 99999)
        self.user_email = f"loadtest_{self.user_id}@example.com"
        self.username = f"loaduser_{self.user_id}"
        self.password = "LoadTest123"
        
        # Register
        with self.client.post("/api/v1/auth/register", 
                              json={
                                  "email": self.user_email,
                                  "username": self.username,
                                  "password": self.password
                              },
                              catch_response=True) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code == 429:
                response.success()  # Rate limited - still ok for load test
            else:
                response.failure(f"Register failed: {response.status_code}")
        
        # Login
        with self.client.post("/api/v1/auth/login",
                              json={
                                  "email": self.user_email,
                                  "password": self.password
                              },
                              catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                response.success()
            elif response.status_code == 429:
                response.success()  # Rate limited - ok
            else:
                response.failure(f"Login failed: {response.status_code}")
    
    @task(3)
    def health_check(self):
        """Health check - most frequent, no auth needed."""
        self.client.get("/health", name="/health")
    
    @task(2)
    def get_metrics(self):
        """Metrics endpoint - monitoring."""
        self.client.get("/metrics", name="/metrics")
    
    @task(2)
    def protected_endpoint(self):
        """Access protected endpoint (needs token)."""
        if self.access_token:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            self.client.get("/api/v1/tasks", headers=headers, name="/api/v1/tasks")
    
    @task(1)
    def register(self):
        """New user registration."""
        random_suffix = random.randint(100000, 999999)
        self.client.post("/api/v1/auth/register",
                         json={
                             "email": f"new_{random_suffix}@example.com",
                             "username": f"newuser_{random_suffix}",
                             "password": "Test123"
                         },
                         name="/api/v1/auth/register")
    
    @task(1)
    def login(self):
        """Login endpoint."""
        if self.user_email:
            self.client.post("/api/v1/auth/login",
                             json={
                                 "email": self.user_email,
                                 "password": self.password
                             },
                             name="/api/v1/auth/login")
    
    @task(1)
    def refresh_token(self):
        """Refresh token endpoint."""
        if self.refresh_token:
            self.client.post(f"/api/v1/auth/refresh?refresh_token={self.refresh_token}",
                             name="/api/v1/auth/refresh")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("\n" + "="*60)
    print("🚀 GATEWAYGUARD LOAD TEST STARTING")
    print("="*60)
    print(f"📊 Test will simulate realistic user behavior")
    print(f"🎯 Target: 50-100 concurrent users")
    print(f"⏱️  Run for 60-120 seconds\n")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print("\n" + "="*60)
    print("✅ GATEWAYGUARD LOAD TEST COMPLETE")
    print("="*60)
    
    # Print summary stats
    stats = environment.stats
    total_requests = stats.total.num_requests
    fail_ratio = stats.total.fail_ratio
    
    print(f"\n📈 SUMMARY STATISTICS:")
    print(f"   Total Requests: {total_requests}")
    print(f"   Failure Ratio: {fail_ratio:.2%}")
    
    if fail_ratio < 0.01:
        print(f"   ✅ EXCELLENT: <1% failure rate")
    elif fail_ratio < 0.05:     print(f"   ⚠️  GOOD: <5% failure rate")  # pyright: ignore[reportUndefinedVariable]
    else:
        print(f"   ❌ POOR: >5% failure rate - needs optimization")
