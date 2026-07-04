# 🔒 GatewayGuard Security Architecture

## Authentication Flow

### Registration
1. Validate input (Pydantic)
2. Check if email exists in DB
3. Hash password (pbkdf2_sha256)
4. Insert user record
5. Return 201 Created

### Login
1. Look up user by email
2. Verify hashed password
3. Generate access token (15 min expiry)
4. Generate refresh token (7 days expiry)
5. Store refresh token in DB
6. Return both tokens

## Password Security

**Algorithm**: pbkdf2_sha256 via passlib

| Algorithm | Security | Performance | Native |
|-----------|----------|-------------|--------|
| **pbkdf2_sha256** | Good | Fast | Pure Python |
| bcrypt | Excellent | Slower | Requires C compiler |
| argon2 | Best | Slowest | External dependency |

Trade-off: pbkdf2_sha256 avoids compilation issues in CI/CD.

**Minimum password length**: 6 characters

## JWT Implementation

### Token Structure
- sub: user_id
- email: user email
- exp: expiration timestamp
- iat: issued-at timestamp
- type: "access"
- jti: UUID v4 (for replay prevention)

### Security Considerations

| Concern | Mitigation |
|---------|------------|
| **Token theft** | Short expiry (15 minutes) |
| **Token tampering** | Signature verification (HS256) |
| **Replay attacks** | jti claim |
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
| **Database breach** | High | Password hashing, no plaintext |
| **Token theft** | High | Short expiry, refresh rotation |
| **DDoS** | Medium | Rate limiting, circuit breakers |
| **JWT secret leak** | Critical | Key rotation, revoke all tokens |
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
