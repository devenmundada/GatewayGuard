<div align="center">

# 🛡️ GatewayGuard

### An API Gateway Deployed Like a Real Service

*A FastAPI gateway running on a 3-node Kubernetes cluster, with automation, monitoring and alerting. Built to learn how services are really operated, failures included.*

[![CI](https://github.com/devenmundada/GatewayGuard/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/devenmundada/GatewayGuard/actions)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-K3s%20v1.36-326CE5?style=flat-square&logo=kubernetes&logoColor=white)](https://k3s.io)
[![Ansible](https://img.shields.io/badge/Ansible-Automated-EE0000?style=flat-square&logo=ansible&logoColor=white)](https://ansible.com)
[![Prometheus](https://img.shields.io/badge/Prometheus-Monitored-E6522C?style=flat-square&logo=prometheus&logoColor=white)](https://prometheus.io)
[![Grafana](https://img.shields.io/badge/Grafana-Live%20Dashboard-F46800?style=flat-square&logo=grafana&logoColor=white)](https://grafana.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## What This Is

GatewayGuard started as a FastAPI application. This repository is the complete infrastructure story of taking that application and deploying it the way real companies do — across multiple servers, fully automated, self-healing, and continuously monitored.

**The question this project answers:** *"You built an app — but can you run it?"*

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MacBook Air (M2)                            │
│                                                                 │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│   │  Ansible │   │ kubectl  │   │   Lens   │   │  Locust  │     │
│   │Automation│   │   CLI    │   │  K8s UI  │   │Load Test │     │
│   └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘     │
└────────┼──────────────┼──────────────┼───────────────┼───────── ┘
         │              │              │               │
         └──────────────┴──────────────┴───────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Kubernetes Cluster  │
                    │       (K3s)           │
                    └───────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  gg-app         │   │  gg-db          │   │  gg-cache       │
│  192.168.252.2  │   │  192.168.252.3  │   │  192.168.252.4  │
│  Control Plane  │   │  Worker Node    │   │  Worker Node    │
│  ─────────────  │   │  ─────────────  │   │  ─────────────  │
│  GatewayGuard   │   │  PostgreSQL 16  │   │  Redis 7        │
│  :30080         │   │  :5432          │   │  :6379          │
│                 │   │                 │   │                 │
│  Subscriber     │   │  Prometheus     │   │                 │
│  Registry :8001 │   │  :30090         │   │                 │
│                 │   │                 │   │                 │
│  Health         │   │  Grafana        │   │                 │
│  Aggregator     │   │  :30030         │   │                 │
│  :8002          │   │                 │   │                 │
└─────────────────┘   └─────────────────┘   └─────────────────┘
```

---

## The Application

GatewayGuard is a JWT-authenticated API gateway built with FastAPI. Everything below is covered by automated tests that run against real PostgreSQL and Redis.

| Feature | What it actually does |
|---------|----------------------|
| Authentication | JWT access tokens (15 min) and refresh tokens (7 days). Refresh tokens are **single-use** (rotated on every refresh) and **stored hashed** (SHA-256). Logout revokes the refresh token and the current access token (its `jti` goes on a Redis revocation list until it would expire anyway). |
| Rate limiting | Fixed window, enforced in Redis by one atomic Lua script, so workers and pods share one counter. Limits: 10/min on auth endpoints, 100/min anonymous (per IP), 200/min per logged-in user. Returns `429` with `Retry-After`. `/health*` and `/metrics` are exempt. |
| Resilience | The Redis calls of the rate limiter run behind a circuit breaker (CLOSED, OPEN, HALF-OPEN). When Redis is down the limiter switches to a per-process memory fallback immediately and returns to Redis by itself when it recovers. |
| Database outage | PostgreSQL unreachable gives `503` + `Retry-After`, never a fake `401`, and `/health/ready` fails so Kubernetes stops sending traffic. There is no in-memory database fallback. |
| Tasks API | Real CRUD (`/api/v1/tasks`) with pagination, a `completed` filter and per-user ownership (another user's task id returns `404`). |
| Observability | JSON logs with a correlation id (`X-Request-ID`) on every request, including rejected ones. Prometheus metrics: `http_requests_total`, `http_request_duration_seconds`, `http_rate_limited_total`, aggregated correctly across all gunicorn workers. |
| Health | `/health/live` (process is up, never touches the database), `/health/ready` and `/health` (PostgreSQL required, Redis optional). |
| Schema | Alembic migrations (`scripts/migrate.py`); CI runs them and fails if the models drift from the migrations. |
| Config safety | With `ENVIRONMENT=production` the app **refuses to start** without a random `JWT_SECRET` of 32+ characters. |

### Request path

Every request passes through the layers in this order (outermost first):

```
CORS -> CorrelationID -> Logging -> Metrics -> Auth -> RateLimiter -> route
```

CORS is outermost so even `401`/`429` responses carry CORS headers. Correlation id, logging and metrics sit outside auth and the limiter so rejected requests are still identified, logged and counted. Auth runs before the limiter so logged-in users get their own per-user bucket.

### Known limitations (honest list)

- **Memory fallback is per process.** While Redis is down, each of the N workers counts separately, so the effective limit is up to N times higher.
- **Access-token revocation fails open.** If Redis is down, a logged-out access token keeps working until its 15 minute expiry.
- **Fixed-window limiting** allows up to 2x the limit across a window boundary.
- **Single replica** of the app on one node (`gg-app`); a node failure is an outage.
- **`/metrics` is unauthenticated** (Prometheus scrapes it over the NodePort). Fine for a lab network, not for the internet.
- **Registration reveals whether an email or username is taken** (one combined message, rate limited at 10/min).
- The load-test numbers further down were measured on the first version, before the connection pool, metrics and limiter changes; re-measure before quoting them.

---

## Infrastructure — 7 Phases

### Phase 0 — Linux Server Setup
Provisioned 3 Ubuntu VMs using Multipass. Manually configured firewalls, SSH, and system security on each — no scripts, no shortcuts — to build genuine Linux fluency before automating anything.

### Phase 1 — Manual Multi-Node Deployment
Deployed GatewayGuard across 3 physically separate VMs with each service on its own machine. Configured real network communication between them using actual IP addresses, not localhost shortcuts.

```bash
curl http://192.168.252.2:8000/health
# → {"status":"healthy","checks":{"database":"ok","redis":"ok","gateway":"ok"}}
```

**Real problems hit:** asyncpg version incompatibility with Python 3.13, missing gunicorn in production container. Both diagnosed from error output and fixed.

### Phase 2 — Ansible Automation
Wrote idempotent Ansible playbooks that reproduce the entire Phase 1 deployment automatically. One command provisions all 3 servers simultaneously from scratch.

```bash
ansible-playbook -i hosts.ini deploy.yml
# First run:  changed=1 on each machine
# Second run: changed=0 on every machine — fully idempotent
```

### Phase 3 — Companion Services

Built two telecom-flavored companion services to extend the architecture:

**Subscriber Registry** (port 8001) — Tracks active subscriber sessions with create, read, delete, and list operations. Conceptually equivalent to a telecom Home Subscriber Server (HSS).

**Health Aggregator** (port 8002) — Single endpoint that polls all services and returns a unified health report with per-service response times.

```json
{
  "overall_status": "healthy",
  "services": {
    "gatewayguard": { "status": "ok", "response_time_ms": 32.02 },
    "subscriber_registry": { "status": "ok", "response_time_ms": 2.56 }
  }
}
```

### Phase 4 — Kubernetes (K3s)

Installed K3s across all 3 VMs to form a real Kubernetes cluster. Migrated GatewayGuard from plain Docker to a managed Kubernetes Deployment.

**Cluster topology:**
- `gg-app` → control plane (API server, scheduler, controller manager)
- `gg-db` → worker node
- `gg-cache` → worker node

**What Kubernetes adds over plain Docker:**

| Capability | Before (Docker) | After (Kubernetes) |
|------------|-----------------|-------------------|
| Crash recovery | Manual restart | Automatic within seconds |
| Health checking | None | Liveness + readiness probes |
| Secret management | Plaintext in files | Kubernetes Secrets, injected at runtime |
| Scheduling | Manual per-machine | Automatic across cluster |

**Self-healing demonstrated:** Deleted a running pod in Lens → Kubernetes detected replica count dropped below desired → new pod running within 10 seconds. Zero human intervention.

**Probes:** the kubelet calls two different endpoints. `/health/live` (liveness) only says the process is up, so a database outage can never put pods into a restart loop. `/health/ready` (readiness) checks PostgreSQL; while it fails the pod is removed from the Service but not restarted. This was verified by stopping PostgreSQL: readiness went to 503, liveness stayed 200, and no pod restarted.

**Kubernetes Secrets:** Removed all plaintext credentials from YAML files. Database URL and Redis URL stored as a Secret, injected into the container at startup. Deployment files are now safe to commit publicly.

### Phase 5 — Prometheus + Grafana Monitoring

Deployed a full monitoring stack as Kubernetes pods — meaning they self-heal just like GatewayGuard.

**Data flow:**
```
GatewayGuard /metrics → Prometheus (every 15s) → Grafana → Browser
```

**Live dashboard panels:**
- Memory usage in bytes — shows real RAM consumption over time
- CPU time — shows processing load
- GC activity rate — shows Python garbage collection across 3 generations

**Persistent storage:** Grafana dashboards and Prometheus time series each live on a PersistentVolumeClaim, so they survive pod restarts.

### Phase 6 — Alerting

Prometheus evaluates alert rules (`GatewayGuardDown`, `GatewayGuardHighErrorRate`) and sends them to Alertmanager, which delivers FIRING and RESOLVED messages to Telegram. The bot token is a Kubernetes Secret mounted as a file, never in git. The `GatewayGuardDown` path was tested end to end (FIRING and RESOLVED messages both arrived on Telegram); the error-rate rule is defined but has not been triggered yet.

---

## Load Test Results

Ran with Locust: 50 concurrent users, 120 seconds, real Kubernetes cluster.

```
Total Requests    1,438
Duration          120 seconds  
Sustained Rate    12 req/s
Median Latency    6ms
95th Percentile   13ms
99th Percentile   41ms
```

| Endpoint | Requests | Failure Rate | Note |
|----------|----------|-------------|------|
| GET /health | 762 | 0% | Rate-limit exempt |
| GET /metrics | 541 | 0% | Rate-limit exempt |
| POST /login | 288 | 82% | 429 — rate limiter working |
| POST /register | 273 | 81% | 429 — rate limiter working |

**The 26% overall "failure" rate is the rate limiter working correctly** — every "failure" is a 429 Too Many Requests on auth endpoints, not an application crash. Zero system errors. Health and metrics endpoints maintained 0% failure rate throughout.

**Grafana during the load test:**
- Memory jumped from 94MB → 102MB the moment traffic hit
- CPU slope steepened immediately
- GC activity spiked from near-zero to constant rapid bursts

---

## Real Problems Hit and Fixed

Every problem below is a real production issue that experienced engineers encounter:

| Problem | What Happened | Root Cause | Fix |
|---------|--------------|------------|-----|
| K3s stuck activating | Service stayed in `activating` state for 5+ minutes | 1 CPU insufficient — SQLite too slow to initialize | Increased control plane to 2 CPUs |
| Worker nodes not joining | `kubectl get nodes` showed only 1 node after joining | UFW firewall blocking ports 6443, 8472/udp, 10250 | Opened all three ports |
| Pod stuck Pending | `Container image not present` error | Containerd uses fully-qualified image names (`docker.io/library/`) — Docker allows short names | Updated image name in Deployment |
| 27 pod restarts | Liveness probe kept failing, triggering restart loop | Rate limiter blocked Kubernetes health checks (same IP hitting /health 5-10x/sec → 429) | Exempted /health and /metrics from rate limiting |
| Grafana dashboards lost | Dashboard gone after every pod restart | Pod storage is ephemeral — data lives inside the container | Added PersistentVolumeClaim backed by node disk |
| Disk pressure taint | Grafana stuck in Pending, `0/3 nodes available` | After 3 weeks idle, disk hit 63% — Kubernetes auto-tainted the node | Pruned unused images, removed taint with `kubectl taint nodes gg-db ... -` |
| Prometheus showing no data | All queries returned empty results | VM clock drifted 4 days while idle — timestamps didn't align with browser time | `chronyc makestep` to force immediate clock sync |
| asyncpg build failure | Docker build failed | asyncpg 0.29.0 incompatible with Python 3.13 | Updated to asyncpg 0.30.0 |
| gunicorn not found | Container crashed immediately on start | gunicorn missing from requirements.txt | Added gunicorn to requirements.txt |
| CI hung for 4 hours | A request that hit a database error never returned | The rate limiter middleware called `call_next` a second time inside its `except` block after the app had already raised | Restructured so only the limiter's own logic is inside `try`; added `--timeout=60` to pytest |
| `ErrImageNeverPull` | Port 30080 refused connections | The image had vanished from K3s's containerd store (Docker and K3s keep separate image stores) | Re-imported with `docker save \| k3s ctr images import -`; `start.sh` now checks for it |
| Pods on workers could not resolve DNS | Cross-node requests timed out | Flannel (8472/udp) and kubelet (10250) were blocked by ufw on `gg-db` / `gg-cache` | Opened the ports; `start.sh` and the Ansible playbook now do it |
| Health check said "healthy" with the database down | Stopping PostgreSQL changed nothing in `/health` | The endpoint returned a hard-coded response | Real checks: readiness runs `SELECT 1` and pings Redis |

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | FastAPI + Starlette | 0.143 / 1.7 |
| Server | Gunicorn + Uvicorn workers | 23 / 0.30 |
| Database | PostgreSQL | 16 |
| Cache | Redis | 7 |
| ORM / migrations | SQLAlchemy (async) + Alembic | 2.0 / 1.13 |
| Auth | PyJWT + passlib (PBKDF2-SHA256) | 2.15 / 1.7 |
| Containers | Docker + containerd | — |
| Orchestration | Kubernetes (K3s) | v1.36.3 |
| Automation | Ansible | — |
| Monitoring | Prometheus + Alertmanager + Grafana | — |
| Load Testing | Locust | 2.x |
| CI/CD | GitHub Actions | — |
| VM Management | Multipass | Ubuntu 26.04 ARM64 |

---

## Repository Structure

```
GatewayGuard/
├── app/
│   ├── api/                 # health, metrics, v1/auth, v1/tasks, deps
│   ├── core/                # JWT + passwords, rate limiter, circuit breaker, token revocation
│   ├── db/                  # models, CRUD, async engine/pool
│   ├── middleware/          # correlation id, logging, metrics, auth, rate limiter
│   ├── schemas/             # request/response models
│   ├── services/            # Redis client
│   └── utils/               # logging, client IP
├── migrations/              # Alembic migrations (0001 initial, 0002 hashed refresh tokens)
├── scripts/
│   ├── migrate.py           # runs migrations (also adopts a pre-Alembic database)
│   ├── deploy.sh            # build image on gg-app, migrate, roll out
│   └── start.sh             # bring the cluster back after a break
├── kubernetes/              # app, service, migrate job, monitoring (Prometheus, Alertmanager, Grafana)
├── ansible/                 # legacy Docker-based provisioning (secrets via secrets.yml)
├── services/                # companion services (subscriber registry, health aggregator)
├── tests/                   # 60+ tests against real PostgreSQL and Redis
├── Dockerfile.prod          # non-root, health-checked, no compiler, no tests inside
├── gunicorn.conf.py         # workers + Prometheus multiprocess cleanup
├── requirements.txt         # runtime dependencies (exact pins)
└── requirements-dev.txt     # test / lint / audit tools
```

---

## Local Development

```bash
git clone https://github.com/devenmundada/GatewayGuard.git
cd GatewayGuard

python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
docker compose up -d                       # PostgreSQL (port 5433) + Redis
python scripts/migrate.py                  # create / update tables
uvicorn app.main:app --reload --port 8000
```

| URL | Purpose |
|-----|---------|
| `http://localhost:8000/docs` | Swagger UI (disabled when `ENVIRONMENT=production`) |
| `http://localhost:8000/health/ready` | Readiness (database + Redis) |
| `http://localhost:8000/metrics` | Prometheus metrics |

Running the tests needs PostgreSQL and Redis running and migrated, with `ENVIRONMENT=testing`:

```bash
ENVIRONMENT=testing python scripts/migrate.py
pytest tests/ -v
```

---

## Deploying to the cluster

```bash
./scripts/deploy.sh      # generates JWT_SECRET if missing, builds, migrates, rolls out
```

---

## CI Pipeline

GitHub Actions runs on every push and pull request. Every job is blocking.

| Job | What it checks |
|-----|---------------|
| Tests | Migrations applied to a real PostgreSQL, `alembic check` (models match migrations), full pytest suite with Redis |
| Lint | `ruff check` (no auto-fix) |
| Dependency audit | `pip-audit` on `requirements.txt`; any known vulnerability fails the build |
| Docker image | Builds `Dockerfile.prod`, checks it refuses to start with the default secret, runs as non-root, and answers `/health/live` |

---

<div align="center">

## Author

**Deven Mundada**

Built as a complete hands-on infrastructure engineering project — every line of configuration written, every problem debugged, every concept understood from first principles.

[![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/devenmundada)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat-square&logo=linkedin&logoColor=white)](https://linkedin.com/in/devenmundada)

---

*"I build reliable systems that survive failures — not just code, but the infrastructure it runs on."*

</div>
