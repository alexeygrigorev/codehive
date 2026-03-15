"""Pydantic schemas for Checkpoint API endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CheckpointCreate(BaseModel):
    """Request body for POST /api/sessions/{session_id}/checkpoints."""

    label: str | None = Field(default=None, max_length=500)


class CheckpointRead(BaseModel):
    """Response schema for a single checkpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    git_ref: str
    state: dict
    created_at: datetime
