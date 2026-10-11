"""
Records request count and latency for Prometheus.
"""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.api.metrics import REQUEST_DURATION, REQUESTS


def _endpoint_label(request: Request) -> str:
    """
    Label with the route template ("/api/v1/tasks/{task_id}"), not the raw path, so ids
    do not create unbounded label values. Unmatched paths (scanners hitting random URLs,
    or requests rejected before routing) share one label for the same reason.

    The template is rebuilt from the real path and the matched path parameters because
    route.path is relative to its router (it would say "/{task_id}") and differs between
    Starlette versions.
    """
    if request.scope.get("route") is None:
        return "unmatched"
    parts = request.url.path.split("/")
    for name, value in request.scope.get("path_params", {}).items():
        for i in range(len(parts) - 1, -1, -1):
            if parts[i] == str(value):
                parts[i] = "{" + name + "}"
                break
    return "/".join(parts) or "/"


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500  # if the app raises, the client gets a 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            endpoint = _endpoint_label(request)
            REQUESTS.labels(request.method, endpoint, str(status_code)).inc()
            REQUEST_DURATION.labels(request.method, endpoint).observe(
                time.perf_counter() - start
            )
