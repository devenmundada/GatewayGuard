# 🏗️ GatewayGuard System Architecture

## Table of Contents
1. [High-Level Overview](#high-level-overview)
2. [System Components](#system-components)
3. [Request Flow](#request-flow)
4. [Data Flow Diagram](#data-flow-diagram)
5. [Failure Handling](#failure-handling)
6. [Technology Stack](#technology-stack)

## High-Level Overview

GatewayGuard is a **production-grade API gateway** that implements the **Gateway pattern** for microservice architectures. It serves as the single entry point for all client traffic, handling cross-cutting concerns including authentication, rate limiting, circuit breaking, and observability.

### Core Principles

1. **Separation of Concerns**: Each middleware handles exactly one responsibility
2. **Graceful Degradation**: System remains operational even when dependencies fail
3. **Observability by Default**: Every request is traceable via correlation IDs
4. **Security First**: All authentication is handled at the edge

## System Components

### 1. FastAPI Application (Core)

**Role**: HTTP request routing and processing engine.

**Implementation Details**:
- **Framework**: FastAPI (ASGI-based)
- **Server**: Gunicorn managing Uvicorn workers (2 by default, `WEB_CONCURRENCY` to change)
- **Middleware Stack**: Chain of Responsibility pattern
- **Dependency Injection**: Built-in FastAPI DI for database sessions and Redis clients

### 2. Middleware Components

#### a. Correlation ID Middleware

**Role**: Inject unique trace identifiers into every request.

#### b. Logging Middleware

**Role**: Record structured logs with correlation IDs and performance metrics.

#### c. Auth Middleware

**Role**: Validate JWT tokens and extract user identity.

**Public paths** (exact match): `/`, `/health`, `/health/live`, `/health/ready`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`, and `/api/v1/auth/{register,login,refresh,logout}`.

**Order** (outermost first): CORS, CorrelationID, Logging, Metrics, Auth, RateLimiter, route. Starlette wraps in reverse of registration, so `main.py` registers them in the opposite order.

#### d. Rate Limiter Middleware

**Role**: Enforce request limits using Redis with memory fallback.

**Limits**:
- Auth endpoints: 10/min
- Public endpoints: 100/min
- Authenticated users: 200/min

### 3. Service Layer

#### a. PostgreSQL (User Data, Tasks, Refresh Tokens)

Tables: users, tasks, refresh_tokens

#### b. Redis (Rate Limiting State)

Key Structure:
- rl:ip:{ip_address} — IP-based rate limiting
- rl:user:{user_id} — User-based rate limiting

#### c. Memory Fallback

Used while the circuit breaker around Redis is OPEN. Per-process fixed-window counters; see rate-limiting.md.

## Failure Handling

| Failure Scenario | Detection | Recovery |
|-----------------|-----------|----------|
| **Redis Down** | Circuit breaker opens after 3 failures (1 s socket timeout) | In-memory fallback; retried automatically after 10 s |
| **PostgreSQL Down** | Connect error / pool timeout (5 s) | 503 + `Retry-After`; `/health/ready` fails so Kubernetes removes the pod from the Service (liveness is unaffected, no restarts) |
| **JWT Expired** | Signature verification fails | 401 with refresh guidance |
| **Rate Limit Exceeded** | Counter > limit | 429 with `Retry-After` |

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Framework** | FastAPI / Starlette | 0.143.0 / 1.7.0 | Async web framework |
| **Server** | Uvicorn | 0.30.0 | ASGI server |
| **ORM** | SQLAlchemy | 2.0.35 | Async database ORM |
| **Database** | PostgreSQL | 16.0 | Primary data store |
| **Cache** | Redis | 7.0 | Rate limiting state |
| **Auth** | PyJWT | 2.15.1 | JWT handling |
| **Hashing** | passlib | 1.7.4 | Password hashing |
| **Logging** | python-json-logger | 2.0.7 | Structured logging |
| **Metrics** | prometheus-client | 0.20.0 | Prometheus exposition |
| **Testing** | pytest | 9.1.1 | Unit & integration tests |
| **Container** | Docker | Latest | Containerization |
| **CI/CD** | GitHub Actions | Latest | Automated pipeline |
