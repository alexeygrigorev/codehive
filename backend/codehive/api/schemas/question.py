"""Pydantic schemas for Pending Questions API endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuestionAnswer(BaseModel):
    """Request body for POST /api/sessions/{session_id}/questions/{question_id}/answer."""

    answer: str = Field(..., min_length=1)


class QuestionRead(BaseModel):
    """Response schema for a single pending question."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    question: str
    context: str | None
    answered: bool
    answer: str | None
    created_at: datetime
