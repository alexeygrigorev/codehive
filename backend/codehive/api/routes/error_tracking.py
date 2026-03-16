"""REST endpoints for the error tracking dashboard."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.errors import ErrorCountByType, ErrorEvent, ErrorSummary
from codehive.core.error_tracking import ErrorTracker

router = APIRouter(prefix="/api/errors", tags=["errors"])


def _get_tracker() -> ErrorTracker:
    """Return an ErrorTracker instance."""
    return ErrorTracker()


@router.get("/summary", response_model=ErrorSummary)
async def error_summary(
    db: AsyncSession = Depends(get_db),
    tracker: ErrorTracker = Depends(_get_tracker),
) -> ErrorSummary:
    """Return error summary: total count, window count, rate, spike status."""
    summary = await tracker.get_summary(db)
    return ErrorSummary(**summary)


@router.get("/by-type", response_model=list[ErrorCountByType])
async def errors_by_type(
    after: datetime | None = Query(default=None),
    before: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    tracker: ErrorTracker = Depends(_get_tracker),
) -> list[ErrorCountByType]:
    """Return error counts grouped by event type."""
    rows = await tracker.get_errors_by_type(db, after=after, before=before, limit=limit)
    return [ErrorCountByType(**row) for row in rows]


@router.get("/recent", response_model=list[ErrorEvent])
async def recent_errors(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    tracker: ErrorTracker = Depends(_get_tracker),
) -> list[ErrorEvent]:
    """Return recent error events, most recent first."""
    events = await tracker.get_recent_errors(db, limit=limit, offset=offset, event_type=event_type)
    return [ErrorEvent.model_validate(e) for e in events]
