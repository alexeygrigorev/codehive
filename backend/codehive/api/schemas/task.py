"""Pydantic schemas for Task queue API endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VALID_PIPELINE_STATUSES = frozenset(
    {"backlog", "grooming", "groomed", "implementing", "testing", "accepting", "done"}
)

PipelineStatusLiteral = Literal[
    "backlog", "grooming", "groomed", "implementing", "testing", "accepting", "done"
]


class TaskCreate(BaseModel):
    """Request body for POST /api/sessions/{session_id}/tasks."""

    title: str = Field(..., max_length=500)
    instructions: str | None = None
    priority: int = 0
    depends_on: uuid.UUID | None = None
    mode: str = Field(default="auto", max_length=50)
    created_by: str = Field(default="user", max_length=50)
    pipeline_status: PipelineStatusLiteral = "backlog"


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


class PipelineTransitionRequest(BaseModel):
    """Request body for POST /api/tasks/{id}/pipeline-transition."""

    status: str
    actor: str | None = Field(default=None, max_length=255)


class TaskPipelineLogRead(BaseModel):
    """Response schema for a pipeline log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    from_status: str
    to_status: str
    actor: str | None
    created_at: datetime


class TaskRead(BaseModel):
    """Response schema for a single task."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    title: str
    instructions: str | None
    status: str
    pipeline_status: str
    priority: int
    depends_on: uuid.UUID | None
    mode: str
    created_by: str
    created_at: datetime
