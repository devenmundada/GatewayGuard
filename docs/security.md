# 🔒 GatewayGuard Security Architecture

## Authentication Flow

### Registration
1. Validate input (Pydantic)
2. Check if the email or username exists (one combined error message)
3. Hash password (pbkdf2_sha256)
4. Insert user record
5. Return 201 Created

### Login
1. Look up user by email
2. Verify the password (a dummy hash is checked when the email is unknown, so timing does not reveal which emails exist)
3. Generate access token (15 min expiry)
4. Generate refresh token (7 days expiry)
5. Store the SHA-256 hash of the refresh token in the DB (never the token)
6. Return both tokens

## Password Security

**Algorithm**: pbkdf2_sha256 via passlib

| Algorithm | Security | Performance | Native |
|-----------|----------|-------------|--------|
| **pbkdf2_sha256** | Good | Fast | Pure Python |
| bcrypt | Excellent | Slower | Requires C compiler |
| argon2 | Best | Slowest | External dependency |

Trade-off: pbkdf2_sha256 avoids compilation issues in CI/CD.

**Password length**: 8 to 128 characters (the upper bound stops huge inputs from becoming a hashing denial of service)

## JWT Implementation

### Token Structure
- sub: user_id
- email: user email
- exp: expiration timestamp
- iat: issued-at timestamp
- type: "access"
- jti: UUID v4 (used to revoke an access token on logout)

### Security Considerations

| Concern | Mitigation |
|---------|------------|
| **Token theft** | Short expiry (15 minutes) |
| **Token tampering** | Signature verification (HS256, algorithm pinned server-side, `exp` and `sub` required) |
| **Stolen token after logout** | `jti` goes on a Redis revocation list until the token expires (fails open if Redis is down) |
| **Token leakage** | TLS/HTTPS in production |

## Refresh Token Strategy

Lifecycle: Created on login → Active → Revoked (on logout/rotation) or Expired (7 days)

On refresh:
1. Validate refresh token
2. Revoke old token
3. Issue new access + refresh tokens
4. Store new refresh token

## Threat Model

| Attack | Risk Level | Mitigation |
|--------|------------|------------|
| **Database breach** | High | Passwords hashed (PBKDF2), refresh tokens stored only as SHA-256 hashes |
| **Token theft** | High | Short expiry, refresh rotation |
| **DDoS** | Medium | Rate limiting, circuit breakers |
| **JWT secret leak** | Critical | App refuses to start in production without a random 32+ character secret (from a Kubernetes Secret); rotating the secret invalidates every token |
| **SQL injection** | Medium | SQLAlchemy ORM |
| **MITM** | Medium | HTTPS in production |

## Best Practices

1. Never log passwords or JWT secrets
2. Use environment variables for secrets
3. Regular key rotation for JWT secrets
4. Log all authentication failures for audit
5. Use HTTPS in production (TLS 1.2+)
6. Validate all inputs (Pydantic)
7. Keep dependencies updated (pip audit)

## Tokens never travel in URLs

`/auth/refresh` and `/auth/logout` take the refresh token in the JSON body. Query strings end up in access logs, proxies and browser history.

## Known gaps

- No refresh-token reuse detection (replaying an already-rotated token is rejected, but it does not revoke the user's other sessions).
- No account lockout; brute force is limited only by the 10/min per-IP auth limit.
- `/metrics` is unauthenticated.
- HS256 with one shared secret; asymmetric keys (RS256) would let other services verify tokens without being able to mint them.
