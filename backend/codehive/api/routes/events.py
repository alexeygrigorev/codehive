"""REST endpoints for historical event queries."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.event import EventRead
from codehive.core.events import EventBus, SessionNotFoundError

router = APIRouter(prefix="/api/sessions", tags=["events"])


def _get_event_bus() -> EventBus:
    """Return an EventBus with a dummy Redis (REST queries don't need Redis)."""
    # The REST endpoint only reads from the DB, so we pass None for Redis.
    # The EventBus.get_events method does not use Redis.
    return EventBus(redis=None)  # type: ignore[arg-type]


@router.get("/{session_id}/events", response_model=list[EventRead])
async def list_events(
    session_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    event_bus: EventBus = Depends(_get_event_bus),
) -> list[EventRead]:
    """Return historical events for a session, ordered by created_at ascending."""
    try:
        events = await event_bus.get_events(db, session_id, limit=limit, offset=offset)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    return [EventRead.model_validate(e) for e in events]
