"""Pydantic schemas for transcript export endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class TranscriptEntry(BaseModel):
    """A single transcript item: message or tool call."""

    type: str  # "message" or "tool_call"
    timestamp: datetime
    role: str | None = None
    content: str | None = None
    tool_name: str | None = None
    input: str | None = None
    output: str | None = None
    is_error: bool | None = None


class TranscriptExportJSON(BaseModel):
    """JSON export response for a session transcript."""

    session_id: uuid.UUID
    session_name: str
    status: str
    engine: str
    mode: str
    created_at: datetime
    exported_at: datetime
    entry_count: int
    entries: list[TranscriptEntry]


class TranscriptExportMarkdown(BaseModel):
    """Markdown export response for a session transcript."""

    content: str
