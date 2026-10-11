# 🚦 GatewayGuard Rate Limiting

## Algorithm: fixed window counter

For each key (IP or user id) there is one counter that lives for one window (60 s).
When the counter exceeds the limit, requests get `429`.

**Pros**: simple, one counter per key, atomic in Redis, TTL cleans up by itself.
**Cons**: burst problem. Just before and just after a window boundary, up to 2x the limit can pass.

Alternatives considered: sliding window (more accurate, more memory), token bucket, GCRA. Not needed at this scale.

## Redis implementation

One Lua script runs atomically inside Redis:

```
count = INCR key
if count == 1 then EXPIRE key window end   -- expiry is set once, on the first hit
return count, TTL key
```

Atomic means two workers can never both read "99" and both allow request 100. The expiry is set only on the first hit, so the window really is fixed. (An earlier version did GET, then INCR, then EXPIRE on every hit: racy, and the constant TTL refresh meant a steady trickle never reset.)

### Keys

| Who | Key | Limit |
|-----|-----|-------|
| Logged-in user | `rl:user:{user_id}` | 200 / 60 s |
| Anonymous, auth endpoints | `rl:auth:ip:{ip}` | 10 / 60 s |
| Anonymous, everything else | `rl:default:ip:{ip}` | 100 / 60 s |

`/health*` and `/metrics` are exempt. Responses carry `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and on `429` also `Retry-After`.

### Which IP?

By default the TCP peer address. `X-Forwarded-For` is ignored unless `TRUSTED_PROXY_COUNT` is set to the number of proxies in front of the app, because any client can forge that header to dodge its limit. In Kubernetes the Service uses `externalTrafficPolicy: Local` so the pod sees the real client address instead of the node's.

## Circuit breaker around Redis

The Redis call runs under a circuit breaker (`app/core/circuit_breaker.py`):

| State | Behaviour |
|-------|-----------|
| CLOSED | Redis is used. 3 consecutive failures open the breaker. |
| OPEN | Redis is skipped entirely (no socket timeout per request); memory fallback is used. |
| HALF-OPEN | After 10 s one trial call goes to Redis. Success closes the breaker, failure re-opens it. |

So the limiter returns to Redis by itself, with no restart and no background thread.

## Memory fallback

A per-process dict of `key -> (window_start, count)` with the same fixed-window semantics, guarded by a lock and bounded to 10,000 keys.

| Limitation | Explanation |
|------------|-------------|
| Per process | With N gunicorn workers the effective limit while Redis is down is up to N times higher. It keeps the gateway protected, not precise. |
| Lost on restart | Counters live in memory. |

## Failure behaviour

- Redis down: breaker opens, memory fallback, `redis` shows `degraded` in `/health/ready` (still ready).
- Limiter code itself raises: the request is let through (fail open) and the error is logged. The app is never called twice.

## Future improvements

1. Sliding window using a Redis sorted set
2. Per-plan limits (free / pro / enterprise)
3. Redis Cluster
