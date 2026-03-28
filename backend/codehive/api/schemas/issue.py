"""Pydantic schemas for Issue CRUD endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from codehive.api.schemas.session import SessionRead


class IssueCreate(BaseModel):
    """Request body for POST /api/projects/{project_id}/issues."""

    title: str = Field(..., max_length=500)
    description: str | None = None
    acceptance_criteria: str | None = None
    assigned_agent: str | None = Field(default=None, max_length=50)
    priority: int = 0


class IssueUpdate(BaseModel):
    """Request body for PATCH /api/issues/{id}."""

    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    acceptance_criteria: str | None = None
    assigned_agent: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, pattern="^(open|groomed|in_progress|done|closed)$")
    priority: int | None = None


class IssueRead(BaseModel):
    """Response schema for a single issue."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    acceptance_criteria: str | None
    assigned_agent: str | None
    status: str
    priority: int
    github_issue_id: int | None
    created_at: datetime
    updated_at: datetime


class IssueLogEntryRead(BaseModel):
    """Response schema for a single issue log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_id: uuid.UUID
    agent_role: str
    agent_profile_id: uuid.UUID | None = None
    agent_name: str | None = None
    agent_avatar_url: str | None = None
    content: str
    created_at: datetime


class IssueLogEntryCreate(BaseModel):
    """Request body for POST /api/issues/{issue_id}/logs."""

    agent_role: str = Field(..., max_length=50)
    content: str


class IssueReadWithSessions(IssueRead):
    """Response schema for a single issue with linked sessions and logs."""

    sessions: list[SessionRead]
    logs: list[IssueLogEntryRead] = []
