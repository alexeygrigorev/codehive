"""Pydantic schemas for Issue CRUD endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from codehive.api.schemas.session import SessionRead


class IssueCreate(BaseModel):
    """Request body for POST /api/projects/{project_id}/issues."""

    title: str = Field(..., max_length=500)
    description: str | None = None


class IssueUpdate(BaseModel):
    """Request body for PATCH /api/issues/{id}."""

    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(open|in_progress|closed)$")


class IssueRead(BaseModel):
    """Response schema for a single issue."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    status: str
    github_issue_id: int | None
    created_at: datetime


class IssueReadWithSessions(IssueRead):
    """Response schema for a single issue with linked sessions."""

    sessions: list[SessionRead]
