"""Pydantic schemas for Workspace CRUD endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    """Request body for POST /api/workspaces."""

    name: str = Field(..., max_length=255)
    root_path: str = Field(..., max_length=1024)
    settings: dict = Field(default_factory=dict)


class WorkspaceUpdate(BaseModel):
    """Request body for PATCH /api/workspaces/{id}."""

    name: str | None = Field(default=None, max_length=255)
    root_path: str | None = Field(default=None, max_length=1024)
    settings: dict | None = None


class WorkspaceRead(BaseModel):
    """Response schema for a single workspace."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    root_path: str
    settings: dict
    created_at: datetime
