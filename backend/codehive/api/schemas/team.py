"""Pydantic schemas for Agent Profile (team) endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from codehive.core.team import avatar_url_for_seed


class AgentProfileCreate(BaseModel):
    """Request body for POST /api/projects/{id}/team."""

    name: str = Field(..., max_length=255)
    role: str = Field(..., max_length=50)
    avatar_seed: str | None = Field(default=None, max_length=255)
    personality: str | None = None
    system_prompt_modifier: str | None = None
    preferred_engine: str | None = Field(default=None, max_length=50)
    preferred_model: str | None = Field(default=None, max_length=255)


class AgentProfileUpdate(BaseModel):
    """Request body for PATCH /api/projects/{id}/team/{agent_id}."""

    name: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=50)
    avatar_seed: str | None = Field(default=None, max_length=255)
    personality: str | None = None
    system_prompt_modifier: str | None = None
    preferred_engine: str | None = Field(default=None, max_length=50)
    preferred_model: str | None = Field(default=None, max_length=255)


class AgentProfileRead(BaseModel):
    """Response schema for a single agent profile."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    role: str
    avatar_seed: str
    avatar_url: str = ""
    personality: str | None
    system_prompt_modifier: str | None
    preferred_engine: str | None
    preferred_model: str | None
    created_at: datetime

    def model_post_init(self, __context: object) -> None:
        """Compute avatar_url from avatar_seed after initialization."""
        if self.avatar_seed and not self.avatar_url:
            self.avatar_url = avatar_url_for_seed(self.avatar_seed)
