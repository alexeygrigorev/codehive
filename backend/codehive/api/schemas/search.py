"""Pydantic schemas for search API endpoints."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class EntityType(str, Enum):
    """Searchable entity types."""

    session = "session"
    message = "message"
    issue = "issue"
    event = "event"


class SearchResultItem(BaseModel):
    """A single search result."""

    model_config = ConfigDict(from_attributes=True)

    type: str
    id: uuid.UUID
    snippet: str
    score: float
    created_at: datetime
    project_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    project_name: str | None = None
    session_name: str | None = None


class SearchResponse(BaseModel):
    """Response for GET /api/search."""

    results: list[SearchResultItem]
    total: int
    has_more: bool


class SessionHistoryItem(BaseModel):
    """A single result from session history search."""

    model_config = ConfigDict(from_attributes=True)

    type: str
    id: uuid.UUID
    snippet: str
    score: float
    created_at: datetime


class SessionHistoryResponse(BaseModel):
    """Response for GET /api/sessions/{id}/history."""

    results: list[SessionHistoryItem]
    total: int
    has_more: bool
