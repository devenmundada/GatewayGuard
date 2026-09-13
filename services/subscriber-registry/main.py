"""
Subscriber Registry Service
Simulates a telecom subscriber/session registry — tracks active sessions,
similar in concept to what an HLR (Home Location Register) does in real
telecom networks.
"""

import os
import uuid
from datetime import datetime

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Subscriber Registry", version="1.0.0")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = None


@app.on_event("startup")
async def startup():
    global redis_client
    redis_client = await redis.from_url(REDIS_URL)


@app.on_event("shutdown")
async def shutdown():
    await redis_client.close()


class SubscriberSession(BaseModel):
    subscriber_id: str
    ip_address: str
    service_type: str = "data"


@app.post("/sessions", status_code=201)
async def create_session(session: SubscriberSession):
    """Register a new subscriber session."""
    session_id = str(uuid.uuid4())
    session_data = {
        "subscriber_id": session.subscriber_id,
        "ip_address": session.ip_address,
        "service_type": session.service_type,
        "created_at": datetime.utcnow().isoformat(),
        "status": "active"
    }
    await redis_client.hset(f"session:{session_id}", mapping=session_data)
    await redis_client.expire(f"session:{session_id}", 3600)
    return {"session_id": session_id, **session_data}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Look up an active subscriber session."""
    data = await redis_client.hgetall(f"session:{session_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return {k.decode(): v.decode() for k, v in data.items()}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Terminate a subscriber session."""
    deleted = await redis_client.delete(f"session:{session_id}")
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session terminated", "session_id": session_id}


@app.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    keys = await redis_client.keys("session:*")
    sessions = []
    for key in keys:
        data = await redis_client.hgetall(key)
        session_id = key.decode().split(":")[1]
        sessions.append({"session_id": session_id, **{k.decode(): v.decode() for k, v in data.items()}})
    return {"active_sessions": len(sessions), "sessions": sessions}


@app.get("/health")
async def health():
    """Health check."""
    try:
        await redis_client.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "error"
    return {"status": "healthy" if redis_status == "ok" else "degraded", "redis": redis_status}
