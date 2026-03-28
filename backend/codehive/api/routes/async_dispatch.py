"""Async (non-blocking) message dispatch for detachable TUI sessions.

Provides ``POST /api/sessions/{id}/messages/async`` which starts the engine
as a background ``asyncio`` task and returns *immediately* with 202 Accepted.
The engine stores events in the DB / publishes to Redis as usual -- clients
reconnect via the existing transcript and WebSocket endpoints.
"""

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.core.usage import persist_chat_event, persist_usage_event
from codehive.api.schemas.session import MessageSend
from codehive.core.session import (
    SessionNotFoundError,
    get_session,
    update_session,
)

logger = logging.getLogger(__name__)

async_dispatch_router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# ---------------------------------------------------------------------------
# Background task registry -- tracked so the server can clean up on shutdown
# ---------------------------------------------------------------------------

_running_tasks: dict[uuid.UUID, asyncio.Task] = {}  # type: ignore[type-arg]


def get_running_tasks() -> dict[uuid.UUID, asyncio.Task]:  # type: ignore[type-arg]
    """Return the module-level running-task registry (for testing / shutdown)."""
    return _running_tasks


class AsyncDispatchResponse(BaseModel):
    status: str


def get_db_factory() -> Any:
    """Return an async session factory for background tasks.

    This is a FastAPI dependency so tests can override it.
    """
    from codehive.db.session import async_session_factory

    return async_session_factory()


async def _run_engine_background(
    session_id: uuid.UUID,
    content: str,
    engine: Any,
    db_factory: Any,
) -> None:
    """Run the engine in the background, updating session status on completion."""
    try:
        # Check if engine already persists events via EventBus
        engine_persists = getattr(engine, "_event_bus", None) is not None

        async with db_factory() as db:
            async for event in engine.send_message(session_id, content, db=db):
                await persist_usage_event(db, session_id, event)
                if not engine_persists:
                    await persist_chat_event(db, session_id, event)

            # Engine finished -- mark as waiting_input
            await update_session(db, session_id, status="waiting_input")
    except Exception as exc:
        logger.exception("Background engine task for session %s failed: %s", session_id, exc)
        try:
            async with db_factory() as db:
                await update_session(db, session_id, status="failed")
        except Exception:
            logger.exception("Failed to mark session %s as failed", session_id)
    finally:
        _running_tasks.pop(session_id, None)


@async_dispatch_router.post(
    "/{session_id}/messages/async",
    response_model=AsyncDispatchResponse,
    status_code=202,
)
async def send_message_async_endpoint(
    session_id: uuid.UUID,
    body: MessageSend,
    db: AsyncSession = Depends(get_db),
    db_factory: Any = Depends(get_db_factory),
) -> AsyncDispatchResponse:
    """Start the engine as a background task and return 202 immediately.

    * Returns ``409 Conflict`` if the session already has a running engine task.
    * Returns ``404`` if the session does not exist.
    """
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Reject if already running
    if session_id in _running_tasks and not _running_tasks[session_id].done():
        raise HTTPException(
            status_code=409,
            detail="Session already has a running engine task",
        )

    # Mark session as executing
    try:
        await update_session(db, session_id, status="executing")
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build the engine (import here to match existing pattern in sessions.py)
    from codehive.api.routes.sessions import _build_engine

    try:
        engine = await _build_engine(session.config, engine_type=session.engine)
    except HTTPException:
        await update_session(db, session_id, status="failed")
        raise

    task = asyncio.create_task(
        _run_engine_background(session_id, body.content, engine, db_factory),
    )
    _running_tasks[session_id] = task

    return AsyncDispatchResponse(status="running")
