# GatewayGuard — Production-Grade API Gateway Infrastructure

[![Tests](https://img.shields.io/badge/Tests-17%2F17-brightgreen.svg)](https://github.com/devenmundada/GatewayGuard/actions)
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-K3s%20v1.36-326CE5.svg)](https://k3s.io/)
[![Ansible](https://img.shields.io/badge/Ansible-Automated-EE0000.svg)](https://www.ansible.com/)
[![Prometheus](https://img.shields.io/badge/Prometheus-Monitored-E6522C.svg)](https://prometheus.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A production-grade API gateway deployed across a real 3-node infrastructure — not Docker Compose on a laptop, but a distributed system running across separate Linux servers with full automation, orchestration, and monitoring.

---

## Architecture

\`\`\`
Mac (Ansible / kubectl / Lens)
                ▼
┌─────────────────────────────────────────────┐
│           Kubernetes Cluster (K3s)           │
│                                             │
│  gg-app (192.168.252.2)  — Control Plane   │
│  ├── GatewayGuard pod (port 30080)          │
│  ├── Subscriber Registry (port 8001)        │
│  └── Health Aggregator (port 8002)          │
│                                             │
│  gg-db (192.168.252.3)   — Worker Node     │
│  ├── PostgreSQL (port 5432)                 │
│  ├── Prometheus pod (port 30090)            │
│  └── Grafana pod (port 30030)               │
│                                             │
│  gg-cache (192.168.252.4) — Worker Node    │
│  └── Redis (port 6379)                      │
└─────────────────────────────────────────────┘
\`\`\`

---

## What This Project Demonstrates

| Skill | Evidence |
|-------|----------|
| Linux / Unix | 3 Ubuntu VMs, SSH, firewalls, systemd |
| Networking | Services communicate across real IPs |
| Ansible | One command rebuilds entire environment |
| Docker | Multi-container deployments, custom images |
| Kubernetes | K3s cluster, self-healing, probes, secrets |
| Prometheus | Metrics scraping, PromQL queries |
| Grafana | Live dashboards, persistent storage |
| Load Testing | 50 concurrent users, 6ms median latency |
| Security | Kubernetes Secrets, rate limiting |
| Telecom framing | Subscriber registry (HSS analog) |

---

## The Application

GatewayGuard is a FastAPI-based API gateway with:
- JWT authentication with refresh token rotation
- Redis-backed rate limiting with in-memory fallback
- Circuit breaker pattern
- Structured logging with correlation IDs
- Prometheus metrics at /metrics
- 17 passing automated tests
- Load tested at 50 concurrent users — 6ms median latency

---

## Project Phases

### Phase 0 — Linux Server Setup
Provisioned 3 Ubuntu VMs using Multipass. Configured firewalls, SSH, and basic security on each machine manually to build real Linux fluency.

### Phase 1 — Manual Multi-Node Deployment
Deployed GatewayGuard across 3 separate VMs — app, database, and cache on separate machines. Services communicate using real IP addresses across network boundaries.

\`\`\`bash
curl http://192.168.252.2:8000/health
# {"status":"healthy","checks":{"database":"ok","redis":"ok","gateway":"ok"}}
\`\`\`

### Phase 2 — Ansible Automation
Wrote idempotent Ansible playbooks that fully automate provisioning and deployment across all 3 machines simultaneously. One command rebuilds the entire environment from scratch.

\`\`\`bash
ansible-playbook -i hosts.ini deploy.yml
\`\`\`

### Phase 3 — Companion Services
Built two telecom-flavored services:
- **Subscriber Registry** — tracks active subscriber sessions (analogous to a telecom HSS)
- **Health Aggregator** — single endpoint reporting status of all services

### Phase 4 — Kubernetes (K3s)
Installed K3s across all 3 VMs. Migrated GatewayGuard to a Kubernetes Deployment with:
- Liveness probe: checks /health every 10s, restarts pod on 3 consecutive failures
- Readiness probe: checks /health every 5s, removes from traffic pool if failing
- Kubernetes Secrets: credentials stored securely, never in YAML files
- Self-healing demonstrated: deleted running pod, Kubernetes restarted it in ~10 seconds

### Phase 5 — Prometheus + Grafana Monitoring
Deployed monitoring stack as Kubernetes pods:
- Prometheus scrapes /metrics every 15 seconds
- Grafana displays live dashboards with persistent storage
- Load tested with 50 concurrent users — watched memory, CPU, and GC activity spike live

---

## Load Test Results

\`\`\`
Total Requests:  1,438 in 120 seconds
Request Rate:    12 req/s sustained
Median Latency:  6ms
95th Percentile: 13ms

GET  /health    → 0% failure rate (rate-limit exempt)
GET  /metrics   → 0% failure rate (rate-limit exempt)
POST /login     → 429 rate-limited (correct behavior)
POST /register  → 429 rate-limited (correct behavior)
\`\`\`

The 26% "failure rate" is the rate limiter correctly blocking auth endpoint spam — not crashes. Zero actual application errors.

---

## Real Problems Hit and Fixed

| Problem | Root Cause | Fix |
|---------|-----------|-----|
| K3s stuck activating | 1 CPU insufficient for control plane | Increased to 2 CPUs |
| Worker nodes not joining | UFW firewall blocking ports 6443, 8472, 10250 | Opened required ports |
| Pod stuck Pending | Containerd uses fully-qualified image names | Updated image name in Deployment |
| Rate limiter killing health probes | Kubernetes probes triggered 429s — 27 pod restarts | Exempted /health and /metrics |
| Grafana dashboards lost on restart | Pod storage is ephemeral | Added PersistentVolumeClaim |
| Disk pressure taint | 3 weeks idle accumulated garbage | Pruned images, removed taint |
| Clock skew breaking Prometheus | VM clock drifted while idle | chronyc makestep |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Application | FastAPI, Python, Gunicorn, Uvicorn |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Containers | Docker, containerd |
| Orchestration | Kubernetes (K3s v1.36.3) |
| Automation | Ansible |
| Monitoring | Prometheus, Grafana |
| Load Testing | Locust |
| CI/CD | GitHub Actions |

---

## Repository Structure

\`\`\`
GatewayGuard/
├── app/                    # FastAPI application
├── ansible/                # Ansible playbooks for automation
├── kubernetes/             # Kubernetes manifests
│   ├── gatewayguard-deployment.yaml
│   ├── gatewayguard-service.yaml
│   └── monitoring/
│       ├── prometheus-config.yaml
│       ├── prometheus-deployment.yaml
│       ├── grafana-deployment.yaml
│       └── grafana-pvc.yaml
├── services/               # Companion services
│   ├── subscriber-registry/
│   └── health-aggregator/
├── tests/                  # 17 passing tests
├── locustfile.py           # Load test configuration
└── Dockerfile.prod         # Production Docker image
\`\`\`

---

## Quick Start (Local Development)

\`\`\`bash
git clone https://github.com/devenmundada/GatewayGuard.git
cd GatewayGuard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload --port 8000
\`\`\`

---

## Author

**Deven Mundada** — built as a hands-on infrastructure engineering project targeting Nokia Solution Architect Trainee and infrastructure engineering roles.

[![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat&logo=github&logoColor=white)](https://github.com/devenmundada)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://linkedin.com/in/devenmundada)
