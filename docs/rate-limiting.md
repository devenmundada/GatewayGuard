# 🚦 GatewayGuard Rate Limiting Deep Dive

## Algorithm Selection

### Fixed Window Counter (Chosen)

**How it works**:
1. Maintain a counter for each key (IP or user ID)
2. Counter resets every window (60 seconds)
3. If counter >= limit, block request

**Pros**:
- Simple to implement
- Low memory overhead (one counter per key)
- Atomic operations in Redis
- TTL for automatic cleanup

**Cons**:
- Burst problem: At window boundaries, 2x limit can pass

### Alternatives Considered

- **Sliding Window**: More accurate but memory-heavy. Not chosen.
- **Token Bucket**: Smooths traffic but more complex. Not chosen.
- **GCRA**: Used by Cloudflare. Overkill for our scale.

## Redis Implementation

### Key Strategy

- Authenticated users: rl:user:{user_id}
- Anonymous/IP: rl:ip:{ip_address}

### Limit Configuration

| Scope | Limit | Window | Rationale |
|-------|-------|--------|-----------|
| Auth endpoints | 10 | 60s | Prevent brute-force |
| Public endpoints | 100 | 60s | Basic DDoS protection |
| Authenticated users | 200 | 60s | Higher limit for legitimate users |

## Memory Fallback

### How it works

Uses a Python dict mapping keys to lists of timestamps. On each request:
1. Remove timestamps older than the window
2. Count remaining timestamps
3. If count >= limit, block. Otherwise, append current timestamp.

### Limitations

| Limitation | Explanation | Mitigation |
|------------|-------------|------------|
| **Per-Process** | Each worker has its own dict | Acceptable for small deployments |
| **Memory Bloat** | Stores timestamps, not just counters | Periodic cleanup on each access |
| **No TTL** | Entries persist until cleaned | Clean on each access |

## Failure Scenarios

### Redis Connection Timeout
- Timeout at 2 seconds
- Exception caught, redis_available set to False
- Switches to memory fallback

### Memory Store Growth (estimate)
- 1000 users after 1 hour
- ~60,000 timestamps total
- ~480 KB memory footprint (acceptable)

## Future Improvements

1. **Sliding Window** using Redis Sorted Set
2. **Automatic Redis Recovery** via background thread
3. **Redis Cluster** for horizontal scaling
4. **Dynamic Rate Limits** by user plan (free/pro/enterprise)
5. **Retry-After headers** for rate-limited responses
