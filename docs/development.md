# 🛠️ GatewayGuard Development Guide

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Programming language |
| Docker | Latest | Containerization |
| Docker Compose | Latest | Multi-container orchestration |
| Git | Latest | Version control |

## Setup

```bash
# 1. Clone
git clone https://github.com/devenmundada/GatewayGuard.git
cd GatewayGuard

# 2. Virtual environment
python3.12 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env

# 5. Start dependencies
docker compose up -d

# 6. Run migrations
alembic upgrade head

# 7. Start the app
uvicorn app.main:app --reload --port 8000
```

API available at http://localhost:8000

## Running Tests

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=html
pytest tests/integration/test_auth.py -v
```

## Database Migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

## Load Tests

```bash
uvicorn app.main:app --port 8000
locust -f locustfile.py --host=http://localhost:8000
# Access UI at http://localhost:8089
```

## Debugging

```bash
# Inspect database
docker exec -it gatewayguard-postgres-1 psql -U postgres -d gatewayguard

# Inspect Redis
docker exec -it gatewayguard-redis-1 redis-cli
KEYS rl:*

# View logs
docker compose logs app
```

## Common Issues

| Issue | Fix |
|-------|-----|
| Redis connection failed | docker compose restart redis |
| PostgreSQL connection failed | docker compose logs postgres |
| Port conflict on 8000 | lsof -i :8000 |
