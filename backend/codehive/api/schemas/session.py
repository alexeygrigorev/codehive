"""Pydantic schemas for Session CRUD endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    """Request body for POST /api/projects/{project_id}/sessions."""

    name: str = Field(..., max_length=255)
    engine: str = Field(..., max_length=50)
    mode: str = Field(..., max_length=50)
    issue_id: uuid.UUID | None = None
    parent_session_id: uuid.UUID | None = None
    config: dict = Field(default_factory=dict)


class SessionUpdate(BaseModel):
    """Request body for PATCH /api/sessions/{id}."""

    name: str | None = Field(default=None, max_length=255)
    mode: str | None = Field(default=None, max_length=50)
    config: dict | None = None


class SessionRead(BaseModel):
    """Response schema for a single session."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    issue_id: uuid.UUID | None
    parent_session_id: uuid.UUID | None
    name: str
    engine: str
    mode: str
    status: str
    config: dict
    created_at: datetime
