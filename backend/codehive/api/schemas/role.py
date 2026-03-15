"""Pydantic schemas for Role API endpoints."""

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    """Request body for POST /api/roles."""

    name: str = Field(..., min_length=1, max_length=255)
    display_name: str = ""
    description: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    coding_rules: list[str] = Field(default_factory=list)
    system_prompt_extra: str = ""


class RoleUpdate(BaseModel):
    """Request body for PUT /api/roles/{role_name}."""

    display_name: str | None = None
    description: str | None = None
    responsibilities: list[str] | None = None
    allowed_tools: list[str] | None = None
    denied_tools: list[str] | None = None
    coding_rules: list[str] | None = None
    system_prompt_extra: str | None = None


class RoleRead(BaseModel):
    """Response schema for a single role."""

    name: str
    display_name: str
    description: str
    responsibilities: list[str]
    allowed_tools: list[str]
    denied_tools: list[str]
    coding_rules: list[str]
    system_prompt_extra: str
    is_builtin: bool = False
