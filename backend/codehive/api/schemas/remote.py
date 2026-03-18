"""Pydantic schemas for remote target endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RemoteTargetCreate(BaseModel):
    """Request body for POST /api/remote-targets."""

    label: str = Field(..., max_length=255)
    host: str = Field(..., max_length=500)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(..., max_length=255)
    key_path: str | None = Field(default=None, max_length=1024)
    known_hosts_policy: str = Field(default="auto", max_length=50)


class RemoteTargetUpdate(BaseModel):
    """Request body for PUT /api/remote-targets/{id}."""

    label: str | None = Field(default=None, max_length=255)
    host: str | None = Field(default=None, max_length=500)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    key_path: str | None = Field(default=None, max_length=1024)
    known_hosts_policy: str | None = Field(default=None, max_length=50)


class RemoteTargetRead(BaseModel):
    """Response schema for a single remote target."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    host: str
    port: int
    username: str
    key_path: str | None
    known_hosts_policy: str
    last_connected_at: datetime | None
    status: str
    created_at: datetime


class SSHCommandRequest(BaseModel):
    """Request body for POST /api/remote-targets/{id}/execute."""

    command: str
    timeout: float = Field(default=30.0, gt=0, le=600)


class SSHCommandResult(BaseModel):
    """Response schema for command execution."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class ConnectionStatus(BaseModel):
    """Response schema for connection test."""

    success: bool
    message: str
    duration_ms: float | None = None
