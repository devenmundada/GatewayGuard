<div align="center">

# 🛡️ GatewayGuard

### Production-Grade API Gateway — Built for Real Infrastructure

*Not a tutorial project. A complete, end-to-end system running across 3 real Linux servers with automation, orchestration, and live monitoring.*

[![CI](https://github.com/devenmundada/GatewayGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/devenmundada/GatewayGuard/actions)
[![Tests](https://img.shields.io/badge/Tests-17%2F17%20Passing-brightgreen?style=flat-square)](https://github.com/devenmundada/GatewayGuard/actions)
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

GatewayGuard is a JWT-authenticated API gateway built with FastAPI:

| Feature | Implementation |
|---------|---------------|
| Authentication | JWT with refresh token rotation (15min access / 7day refresh) |
| Rate Limiting | Redis-backed per-user and per-IP limiting with in-memory fallback |
| Resilience | Circuit breaker (CLOSED → OPEN → HALF-OPEN) |
| Observability | Structured JSON logging with correlation IDs across every request |
| Metrics | Prometheus exposition at `/metrics` |
| Health | Liveness + readiness checks at `/health` |
| Tests | 17 passing unit and integration tests |
| Load | 50 concurrent users — 6ms median latency |

---

## Infrastructure — 6 Phases

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

**Probes in action** (visible in live logs):
```
{"path":"/health","client_ip":"10.42.0.1","status_code":200,"duration_ms":4.18}
```
`10.42.0.1` is Kubernetes itself — hitting `/health` every 5-10 seconds automatically.

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

**Persistent storage:** Added a PersistentVolumeClaim so Grafana dashboards survive pod restarts. Before this, every pod restart wiped the dashboard configuration.

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
| gunicorn not found | Container crashed immediately on start | gunicorn missing from requirements.txt | Added gunicorn==22.0.0 |

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | FastAPI | 0.115 |
| Server | Gunicorn + Uvicorn | 22.0 / 0.30 |
| Database | PostgreSQL | 16 |
| Cache | Redis | 7 |
| ORM | SQLAlchemy (async) | 2.0 |
| Auth | python-jose | 3.3 |
| Containers | Docker + containerd | — |
| Orchestration | Kubernetes (K3s) | v1.36.3 |
| Automation | Ansible | — |
| Monitoring | Prometheus + Grafana | — |
| Load Testing | Locust | 2.x |
| CI/CD | GitHub Actions | — |
| VM Management | Multipass | Ubuntu 26.04 ARM64 |

---

## Repository Structure

```
GatewayGuard/
│
├── app/                          # FastAPI application
│   ├── api/v1/                   # Route handlers (auth, tasks)
│   ├── core/                     # Circuit breaker, rate limiter
│   ├── db/                       # Models, CRUD, migrations
│   ├── middleware/               # Auth, logging, rate limiting
│   └── services/                 # Redis client
│
├── ansible/                      # Infrastructure automation
│   ├── deploy.yml                # Main playbook
│   └── ansible.cfg               # Configuration
│
├── kubernetes/                   # Kubernetes manifests
│   ├── gatewayguard-deployment.yaml   # App deployment + probes + secrets
│   ├── gatewayguard-service.yaml      # NodePort service
│   └── monitoring/
│       ├── prometheus-config.yaml     # Scrape configuration (ConfigMap)
│       ├── prometheus-deployment.yaml # Prometheus + NodePort service
│       ├── grafana-deployment.yaml    # Grafana + NodePort service
│       └── grafana-pvc.yaml           # Persistent storage for dashboards
│
├── services/                     # Companion services
│   ├── subscriber-registry/      # Telecom HSS analog (FastAPI + Redis)
│   └── health-aggregator/        # Unified health endpoint (FastAPI + httpx)
│
├── tests/                        # 17 passing tests
├── locustfile.py                 # Load test (50 concurrent users)
├── Dockerfile.prod               # Production container
├── docker-compose.yml            # Local development
└── pyproject.toml                # Tool configuration (ruff, pytest)
```

---

## Local Development

```bash
git clone https://github.com/devenmundada/GatewayGuard.git
cd GatewayGuard

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

docker compose up -d        # Start PostgreSQL + Redis
alembic upgrade head        # Run migrations
uvicorn app.main:app --reload --port 8000
```

| URL | Purpose |
|-----|---------|
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/health` | Health check |
| `http://localhost:8000/metrics` | Prometheus metrics |

```bash
pytest tests/ -v            # Run all 17 tests
```

---

## CI/CD Pipeline

GitHub Actions runs automatically on every push:

| Job | What it checks |
|-----|---------------|
| Lint Check | ruff — code style and quality |
| Security Scan | Dependency vulnerability scanning |
| Test Suite | Full pytest suite against real PostgreSQL + Redis |

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
