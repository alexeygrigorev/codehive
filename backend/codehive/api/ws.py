"""WebSocket endpoint for real-time event streaming via event bus pub/sub."""

import json
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from codehive.api.deps import get_db
from codehive.config import Settings
from codehive.core.events import create_event_bus
from codehive.core.jwt import TokenError, decode_token
from codehive.db.models import Session as SessionModel

router = APIRouter(tags=["events"])

WS_CLOSE_UNAUTHORIZED = 4001
WS_CLOSE_SESSION_NOT_FOUND = 4004


def verify_ws_token(token: str | None) -> dict:
    """Validate a JWT token for WebSocket authentication.

    Returns the decoded payload if the token is a valid, non-expired access
    token. Raises ``TokenError`` for any failure (missing, expired, invalid
    signature, wrong token type).
    """
    if token is None:
        raise TokenError("No token provided")

    payload = decode_token(token)

    if payload.get("type") != "access":
        raise TokenError("Token is not an access token")

    return payload


@router.websocket("/api/sessions/{session_id}/ws")
async def session_events_ws(
    websocket: WebSocket,
    session_id: uuid.UUID,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Stream session events in real-time via the event bus."""
    # --- Authentication ---
    settings = Settings()
    if settings.auth_enabled:
        # Method 1: token as query parameter
        if token is not None:
            try:
                verify_ws_token(token)
            except TokenError:
                raise WebSocketException(code=WS_CLOSE_UNAUTHORIZED, reason="Unauthorized")
        else:
            # Method 2: accept connection, then expect auth as first message
            await websocket.accept()
            try:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                if msg.get("type") != "auth" or "token" not in msg:
                    await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Unauthorized")
                    return
                verify_ws_token(msg["token"])
            except (TokenError, json.JSONDecodeError, KeyError):
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Unauthorized")
                return

    # --- Session lookup ---
    session = await db.get(SessionModel, session_id)
    if session is None:
        if websocket.client_state != WebSocketState.CONNECTED:
            # Query-param auth path: not yet accepted
            raise WebSocketException(code=WS_CLOSE_SESSION_NOT_FOUND, reason="Session not found")
        else:
            # First-message auth path: already accepted
            await websocket.close(code=WS_CLOSE_SESSION_NOT_FOUND, reason="Session not found")
            return

    # Accept connection if not already accepted (query-param auth path)
    if websocket.client_state != WebSocketState.CONNECTED:
        await websocket.accept()

    # Use the event bus subscribe interface (works with both Redis and local)
    bus = create_event_bus(settings.redis_url)

    async with bus.subscribe(session_id) as queue:
        try:
            while True:
                message = await queue.get()
                await websocket.send_text(message)
        except Exception:
            pass
