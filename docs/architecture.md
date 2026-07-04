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
- **Framework**: FastAPI 0.115.0 (ASGI-based)
- **Server**: Uvicorn with multiple workers for concurrency
- **Middleware Stack**: Chain of Responsibility pattern
- **Dependency Injection**: Built-in FastAPI DI for database sessions and Redis clients

### 2. Middleware Components

#### a. Correlation ID Middleware

**Role**: Inject unique trace identifiers into every request.

#### b. Logging Middleware

**Role**: Record structured logs with correlation IDs and performance metrics.

#### c. Auth Middleware

**Role**: Validate JWT tokens and extract user identity.

**Public Paths**: /health, /metrics, /api/v1/auth/register, /api/v1/auth/login

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

Triggered when Redis connection fails. Uses in-memory dict with timestamps.

## Failure Handling

| Failure Scenario | Detection | Recovery |
|-----------------|-----------|----------|
| **Redis Down** | Connection timeout (2s) | In-memory fallback |
| **PostgreSQL Down** | Connection pool exhaustion | 503 Service Unavailable |
| **Downstream Slow** | Request timeout | Circuit breaker opens |
| **JWT Expired** | Signature verification fails | 401 with refresh guidance |
| **Rate Limit Exceeded** | Counter > limit | 429 with retry headers |

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Framework** | FastAPI | 0.115.0 | Async web framework |
| **Server** | Uvicorn | 0.30.0 | ASGI server |
| **ORM** | SQLAlchemy | 2.0.35 | Async database ORM |
| **Database** | PostgreSQL | 16.0 | Primary data store |
| **Cache** | Redis | 7.0 | Rate limiting state |
| **Auth** | python-jose | 3.3.0 | JWT handling |
| **Hashing** | passlib | 1.7.4 | Password hashing |
| **Logging** | python-json-logger | 2.0.7 | Structured logging |
| **Metrics** | prometheus-client | 0.20.0 | Prometheus exposition |
| **Testing** | pytest | 8.0.0 | Unit & integration tests |
| **Container** | Docker | Latest | Containerization |
| **CI/CD** | GitHub Actions | Latest | Automated pipeline |
