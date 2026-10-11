"""
Work out the real client address for rate limiting.
"""
from starlette.requests import Request

from app.config import settings


def get_client_ip(request: Request) -> str:
    """
    With TRUSTED_PROXY_COUNT=0 (default) this is the TCP peer: X-Forwarded-For is
    ignored because any client can send a forged one to dodge its rate limit.

    With N trusted proxies in front, each appends the address it saw, so the real client
    is the Nth entry from the right. Anything further left is client-supplied.
    """
    n = settings.TRUSTED_PROXY_COUNT
    if n > 0:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            if len(hops) >= n:
                return hops[-n]
    return request.client.host if request.client else "unknown"
