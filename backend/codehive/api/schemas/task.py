"""Pydantic schemas for Task queue API endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    """Request body for POST /api/sessions/{session_id}/tasks."""

    title: str = Field(..., max_length=500)
    instructions: str | None = None
    priority: int = 0
    depends_on: uuid.UUID | None = None
    mode: str = Field(default="auto", max_length=50)
    created_by: str = Field(default="user", max_length=50)


class TaskUpdate(BaseModel):
    """Request body for PATCH /api/tasks/{id}."""

    title: str | None = Field(default=None, max_length=500)
    instructions: str | None = None
    priority: int | None = None
    mode: str | None = Field(default=None, max_length=50)
    depends_on: uuid.UUID | None = None


class TaskStatusTransition(BaseModel):
    """Request body for POST /api/tasks/{id}/transition."""

    status: str


class TaskReorderItem(BaseModel):
    """A single item in the reorder request."""

    id: uuid.UUID
    priority: int


class TaskRead(BaseModel):
    """Response schema for a single task."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    title: str
    instructions: str | None
    status: str
    priority: int
    depends_on: uuid.UUID | None
    mode: str
    created_by: str
    created_at: datetime
