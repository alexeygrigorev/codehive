"""Pydantic schemas for the new-project flow endpoints."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from codehive.core.modes import VALID_MODES


class FlowType(str, Enum):
    """Supported project creation flow types."""

    brainstorm = "brainstorm"
    interview = "interview"
    spec_from_notes = "spec_from_notes"
    start_from_repo = "start_from_repo"


class ProjectFlowStart(BaseModel):
    """Request body for POST /api/project-flow/start."""

    flow_type: FlowType
    initial_input: str = ""


class FlowQuestion(BaseModel):
    """A single question posed to the user during the flow."""

    id: str
    text: str
    category: str  # goals / tech / architecture / constraints / team


class FlowAnswer(BaseModel):
    """A single answer from the user."""

    question_id: str
    answer: str


class ProjectFlowRespond(BaseModel):
    """Request body for POST /api/project-flow/{flow_id}/respond."""

    answers: list[FlowAnswer]


class SuggestedSession(BaseModel):
    """A session suggested by the brief."""

    name: str
    mission: str
    mode: str

    @field_validator("mode")
    @classmethod
    def mode_must_be_valid(cls, v: str) -> str:
        if v not in VALID_MODES:
            raise ValueError(f"mode must be one of {sorted(VALID_MODES)}, got '{v}'")
        return v


class ProjectBrief(BaseModel):
    """Generated project brief with all required fields."""

    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    tech_stack: dict[str, Any]
    architecture: dict[str, Any]
    open_decisions: list[dict[str, Any]]
    suggested_sessions: list[SuggestedSession]
    suggested_archetype: str | None = None


class ProjectFlowStartResult(BaseModel):
    """Response for POST /api/project-flow/start."""

    flow_id: uuid.UUID
    session_id: uuid.UUID
    first_questions: list[FlowQuestion]


class ProjectFlowRespondResult(BaseModel):
    """Response for POST /api/project-flow/{flow_id}/respond."""

    next_questions: list[FlowQuestion] | None = None
    brief: ProjectBrief | None = None


class CreatedSession(BaseModel):
    """A session created during finalize."""

    id: uuid.UUID
    name: str
    mode: str


class ProjectFlowFinalizeResult(BaseModel):
    """Response for POST /api/project-flow/{flow_id}/finalize."""

    project_id: uuid.UUID
    sessions: list[CreatedSession]
