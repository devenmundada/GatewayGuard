"""
Prometheus metrics endpoint and metric definitions.

Gunicorn runs several worker processes. prometheus_client keeps counters in each
process's own memory, so a scrape would hit a random worker and Grafana would see
counters jumping up and down. With PROMETHEUS_MULTIPROC_DIR set (the Docker image does
this) every worker writes to shared files and /metrics aggregates them all.
"""
import os

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

router = APIRouter()

REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)
RATE_LIMITED = Counter(
    "http_rate_limited_total",
    "Requests rejected with 429",
    ["tier"],
)


@router.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        data = generate_latest(registry)
    else:
        data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
