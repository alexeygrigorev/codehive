"""Pydantic schemas for error tracking dashboard endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ErrorSummary(BaseModel):
    """Response schema for the error summary endpoint."""

    total_errors: int
    window_errors: int
    window_minutes: int
    errors_per_minute: float
    is_spike: bool


class ErrorCountByType(BaseModel):
    """A single error type with its count."""

    type: str
    count: int


class ErrorEvent(BaseModel):
    """Response schema for a single error event."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    type: str
    data: dict
    created_at: datetime
