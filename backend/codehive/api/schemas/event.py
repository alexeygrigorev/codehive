"""Pydantic schemas for Event endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventRead(BaseModel):
    """Response schema for a single event."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    type: str
    data: dict
    created_at: datetime
