"""Pydantic schemas for Project CRUD endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """Request body for POST /api/projects."""

    name: str = Field(..., max_length=255)
    path: str | None = None
    description: str | None = None
    archetype: str | None = None
    git_init: bool = False


class ProjectUpdate(BaseModel):
    """Request body for PATCH /api/projects/{id}."""

    name: str | None = Field(default=None, max_length=255)
    path: str | None = None
    description: str | None = None
    archetype: str | None = None


class ProjectRead(BaseModel):
    """Response schema for a single project."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    path: str | None
    description: str | None
    archetype: str | None
    knowledge: dict
    created_at: datetime
    archived_at: datetime | None = None
