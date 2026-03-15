"""Pydantic schemas for log query and export endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LogEntry(BaseModel):
    """Response schema for a single log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    type: str
    data: dict
    created_at: datetime


class LogQueryResponse(BaseModel):
    """Paginated response for log queries."""

    items: list[LogEntry]
    total: int
    limit: int
    offset: int


class LogExport(BaseModel):
    """Full export format for session logs."""

    session_id: uuid.UUID
    exported_at: datetime
    event_count: int
    events: list[LogEntry]
