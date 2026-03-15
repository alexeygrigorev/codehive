"""REST endpoint for session replay."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.replay import ReplayResponse, ReplayStep
from codehive.core.events import SessionNotFoundError
from codehive.core.replay import ReplayService, SessionNotReplayableError

replay_router = APIRouter(prefix="/api/sessions", tags=["replay"])


def _get_replay_service() -> ReplayService:
    return ReplayService()


@replay_router.get("/{session_id}/replay", response_model=ReplayResponse)
async def get_session_replay(
    session_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    replay_service: ReplayService = Depends(_get_replay_service),
) -> ReplayResponse:
    """Return paginated replay steps for a completed or failed session."""
    try:
        result = await replay_service.build_replay(
            db,
            session_id,
            limit=limit,
            offset=offset,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except SessionNotReplayableError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return ReplayResponse(
        session_id=result.session_id,
        session_status=result.session_status,
        total_steps=result.total_steps,
        steps=[ReplayStep(**step) for step in result.steps],
    )
