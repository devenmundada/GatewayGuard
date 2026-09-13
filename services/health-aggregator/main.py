"""
Health Aggregator Service
Pings all services and returns a combined health report.
Similar to a Network Management System (NMS) in telecom —
one place to see the status of all network elements.
"""

import os
from datetime import datetime

import httpx
from fastapi import FastAPI

app = FastAPI(title="Health Aggregator", version="1.0.0")

SERVICES = {
    "gatewayguard": os.getenv("GATEWAYGUARD_URL", "http://192.168.252.2:8000/health"),
    "subscriber_registry": os.getenv("SUBSCRIBER_REGISTRY_URL", "http://192.168.252.2:8001/health"),
}


async def check_service(name: str, url: str) -> dict:
    """Ping a single service and return its status."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
            return {
                "status": "ok" if response.status_code == 200 else "degraded",
                "response_time_ms": round(response.elapsed.total_seconds() * 1000, 2),
                "details": response.json()
            }
    except Exception as e:
        return {
            "status": "unreachable",
            "response_time_ms": None,
            "details": str(e)
        }


@app.get("/health")
async def aggregate_health():
    """Check all services and return combined health report."""
    results = {}
    for name, url in SERVICES.items():
        results[name] = await check_service(name, url)

    overall = "healthy" if all(s["status"] == "ok" for s in results.values()) else "degraded"

    return {
        "overall_status": overall,
        "checked_at": datetime.utcnow().isoformat(),
        "services": results
    }
