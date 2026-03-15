"""Pydantic schemas for Session CRUD endpoints."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codehive.core.modes import VALID_MODES

# Modes that are valid for session creation (agent modes + orchestrator)
_VALID_SESSION_MODES = VALID_MODES | {"orchestrator"}


class SessionCreate(BaseModel):
    """Request body for POST /api/projects/{project_id}/sessions."""

    name: str = Field(..., max_length=255)
    engine: str = Field(..., max_length=50)
    mode: str = Field(..., max_length=50)
    issue_id: uuid.UUID | None = None
    parent_session_id: uuid.UUID | None = None
    config: dict = Field(default_factory=dict)

    @field_validator("mode")
    @classmethod
    def mode_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_SESSION_MODES:
            raise ValueError(
                f"Invalid mode '{v}'. Must be one of: {', '.join(sorted(_VALID_SESSION_MODES))}"
            )
        return v


class ModeSwitchRequest(BaseModel):
    """Request body for POST /api/sessions/{session_id}/switch-mode."""

    mode: str

    @field_validator("mode")
    @classmethod
    def mode_must_be_valid(cls, v: str) -> str:
        if v not in VALID_MODES:
            raise ValueError(
                f"Invalid mode '{v}'. Must be one of: {', '.join(sorted(VALID_MODES))}"
            )
        return v


class SessionUpdate(BaseModel):
    """Request body for PATCH /api/sessions/{id}."""

    name: str | None = Field(default=None, max_length=255)
    mode: str | None = Field(default=None, max_length=50)
    config: dict | None = None


class SessionRead(BaseModel):
    """Response schema for a single session."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    issue_id: uuid.UUID | None
    parent_session_id: uuid.UUID | None
    name: str
    engine: str
    mode: str
    status: str
    config: dict
    created_at: datetime


class SubAgentReportStatus(str, Enum):
    """Allowed statuses for a sub-agent report."""

    completed = "completed"
    failed = "failed"
    blocked = "blocked"


class SubAgentReport(BaseModel):
    """Structured report returned by a sub-agent upon completion."""

    status: SubAgentReportStatus
    summary: str
    files_changed: list[str]
    tests: dict[str, int]
    warnings: list[str]

    @field_validator("summary")
    @classmethod
    def summary_must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("summary must be non-empty")
        return v

    @field_validator("tests")
    @classmethod
    def tests_must_have_required_keys(cls, v: dict[str, int]) -> dict[str, int]:
        if "added" not in v or "passing" not in v:
            raise ValueError("tests must have 'added' and 'passing' keys")
        return v


class SessionTreeRead(BaseModel):
    """A session with its direct children."""

    model_config = ConfigDict(from_attributes=True)

    session: SessionRead
    children: list[SessionRead]


class MessageSend(BaseModel):
    """Request body for POST /api/sessions/{session_id}/messages."""

    content: str


class MessageEvent(BaseModel):
    """A single event dict returned from the engine."""

    type: str
    data: dict = Field(default_factory=dict)
