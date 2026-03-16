"""Search API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.search import (
    EntityType,
    SearchResponse,
    SearchResultItem,
    SessionHistoryItem,
    SessionHistoryResponse,
)
from codehive.core.search import SessionNotFoundError, search, search_session_history

search_router = APIRouter(prefix="/api/search", tags=["search"])
session_history_router = APIRouter(prefix="/api/sessions", tags=["search"])

MAX_QUERY_LENGTH = 500


@search_router.get("", response_model=SearchResponse)
async def search_endpoint(
    q: str = Query(..., min_length=1, description="Search query"),
    type: EntityType | None = Query(default=None, description="Filter by entity type"),
    project_id: uuid.UUID | None = Query(default=None, description="Filter by project"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Result offset"),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search across sessions, messages, issues, and events."""
    # Truncate overly long queries
    q_truncated = q[:MAX_QUERY_LENGTH]

    results = await search(
        db,
        q_truncated,
        entity_type=type.value if type else None,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )

    return SearchResponse(
        results=[
            SearchResultItem(
                type=r.type,
                id=r.id,
                snippet=r.snippet,
                score=r.score,
                created_at=r.created_at,
                project_id=r.project_id,
                session_id=r.session_id,
                project_name=r.project_name,
                session_name=r.session_name,
            )
            for r in results.results
        ],
        total=results.total,
        has_more=results.has_more,
    )


@session_history_router.get("/{session_id}/history", response_model=SessionHistoryResponse)
async def session_history_endpoint(
    session_id: uuid.UUID,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Result offset"),
    db: AsyncSession = Depends(get_db),
) -> SessionHistoryResponse:
    """Search within a single session's messages and events."""
    q_truncated = q[:MAX_QUERY_LENGTH]

    try:
        results = await search_session_history(
            db,
            session_id,
            q_truncated,
            limit=limit,
            offset=offset,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionHistoryResponse(
        results=[
            SessionHistoryItem(
                type=r.type,
                id=r.id,
                snippet=r.snippet,
                score=r.score,
                created_at=r.created_at,
            )
            for r in results.results
        ],
        total=results.total,
        has_more=results.has_more,
    )
