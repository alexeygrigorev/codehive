"""Pydantic schemas for session replay endpoint."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReplayStep(BaseModel):
    """A single step in the session replay timeline."""

    index: int
    timestamp: datetime
    step_type: str
    data: dict[str, Any]


class ReplayResponse(BaseModel):
    """Paginated response for session replay."""

    session_id: uuid.UUID
    session_status: str
    total_steps: int
    steps: list[ReplayStep]
