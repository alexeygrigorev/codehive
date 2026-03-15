"""Pydantic schemas for tunnel endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TunnelCreate(BaseModel):
    """Request body for POST /api/tunnels."""

    target_id: uuid.UUID
    remote_port: int = Field(..., ge=1, le=65535)
    local_port: int = Field(..., ge=1, le=65535)
    label: str = Field(default="", max_length=255)


class TunnelRead(BaseModel):
    """Response schema for a single tunnel."""

    id: uuid.UUID
    target_id: uuid.UUID
    remote_port: int
    local_port: int
    label: str
    status: str
    created_at: datetime


class TunnelPreviewURL(BaseModel):
    """Response schema for tunnel preview URL."""

    tunnel_id: uuid.UUID
    url: str
