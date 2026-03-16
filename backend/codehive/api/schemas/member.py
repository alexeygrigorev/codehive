"""Pydantic schemas for workspace membership endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemberAdd(BaseModel):
    """Request body for POST /api/workspaces/{id}/members."""

    user_id: uuid.UUID
    role: str = Field(..., pattern="^(admin|member|viewer)$")


class MemberUpdate(BaseModel):
    """Request body for PATCH /api/workspaces/{id}/members/{user_id}."""

    role: str = Field(..., pattern="^(admin|member|viewer)$")


class MemberRead(BaseModel):
    """Response schema for a workspace membership."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime
