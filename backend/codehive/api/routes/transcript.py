"""REST endpoint for session transcript export."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.transcript import TranscriptExportJSON
from codehive.core.events import SessionNotFoundError
from codehive.core.transcript import TranscriptService
from codehive.db.models import Session as SessionModel

transcript_router = APIRouter(prefix="/api/sessions", tags=["transcript"])


def _get_transcript_service() -> TranscriptService:
    return TranscriptService()


@transcript_router.get("/{session_id}/transcript")
async def export_transcript(
    session_id: uuid.UUID,
    format: str = Query(default="json", description="Export format: json or markdown"),
    db: AsyncSession = Depends(get_db),
    transcript_service: TranscriptService = Depends(_get_transcript_service),
):
    """Export a session transcript as JSON or markdown."""
    if format not in ("json", "markdown"):
        raise HTTPException(
            status_code=400, detail=f"Invalid format: {format}. Must be 'json' or 'markdown'."
        )

    # Verify session exists and check viewer-level access
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        if format == "markdown":
            content = await transcript_service.render_markdown(db, session_id)
            # Sanitize session name for filename
            safe_name = session.name.replace('"', "").replace("/", "-").replace("\\", "-")
            return PlainTextResponse(
                content=content,
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f'attachment; filename="session-{safe_name}.md"',
                },
            )
        else:
            result = await transcript_service.render_json(db, session_id)
            return TranscriptExportJSON(**result)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
