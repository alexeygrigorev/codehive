"""REST endpoints for querying and exporting session logs."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.logs import LogEntry, LogExport, LogQueryResponse
from codehive.core.events import SessionNotFoundError
from codehive.core.logs import LogService

logs_router = APIRouter(prefix="/api/sessions", tags=["logs"])


def _get_log_service() -> LogService:
    return LogService()


@logs_router.get("/{session_id}/logs", response_model=LogQueryResponse)
async def query_logs(
    session_id: uuid.UUID,
    type: str | None = Query(default=None, description="Comma-separated event types"),
    after: datetime | None = Query(default=None, description="ISO datetime lower bound"),
    before: datetime | None = Query(default=None, description="ISO datetime upper bound"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    log_service: LogService = Depends(_get_log_service),
) -> LogQueryResponse:
    """Query session logs with optional type and time-range filters."""
    types: list[str] | None = None
    if type is not None:
        types = [t.strip() for t in type.split(",") if t.strip()]

    try:
        result = await log_service.query(
            db,
            session_id,
            types=types,
            after=after,
            before=before,
            limit=limit,
            offset=offset,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    return LogQueryResponse(
        items=[LogEntry.model_validate(e) for e in result.items],
        total=result.total,
        limit=limit,
        offset=offset,
    )


@logs_router.get("/{session_id}/logs/export", response_model=LogExport)
async def export_logs(
    session_id: uuid.UUID,
    type: str | None = Query(default=None, description="Comma-separated event types"),
    db: AsyncSession = Depends(get_db),
    log_service: LogService = Depends(_get_log_service),
) -> LogExport:
    """Export full session log as JSON."""
    types: list[str] | None = None
    if type is not None:
        types = [t.strip() for t in type.split(",") if t.strip()]

    try:
        events = await log_service.export(db, session_id, types=types)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    return LogExport(
        session_id=session_id,
        exported_at=datetime.now(timezone.utc),
        event_count=len(events),
        events=[LogEntry.model_validate(e) for e in events],
    )
