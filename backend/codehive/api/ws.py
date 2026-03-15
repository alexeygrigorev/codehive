"""WebSocket endpoint for real-time event streaming via Redis pub/sub."""

import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketException
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.config import Settings
from codehive.db.models import Session as SessionModel

router = APIRouter(tags=["events"])


@router.websocket("/api/sessions/{session_id}/ws")
async def session_events_ws(
    websocket: WebSocket,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Stream session events in real-time via Redis pub/sub."""
    # Verify session exists before accepting the connection
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise WebSocketException(code=4004, reason="Session not found")

    await websocket.accept()

    # Import redis here to keep the module importable without Redis running
    from redis.asyncio import Redis

    settings = Settings()
    redis = Redis.from_url(settings.redis_url)
    pubsub = redis.pubsub()
    channel = f"session:{session_id}:events"

    try:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"].decode("utf-8"))
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await redis.close()
