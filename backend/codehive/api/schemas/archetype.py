"""Pydantic schemas for Archetype API endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class ArchetypeRead(BaseModel):
    """Response schema for a single archetype."""

    name: str
    display_name: str
    description: str
    roles: list[str]
    workflow: list[str]
    default_settings: dict[str, Any]
    tech_stack: list[str]
    is_builtin: bool = True


class ArchetypeCloneRequest(BaseModel):
    """Request body for POST /api/archetypes/{name}/clone."""

    name: str = Field(..., min_length=1, max_length=255)
    display_name: str | None = None
    description: str | None = None
    roles: list[str] | None = None
    workflow: list[str] | None = None
    default_settings: dict[str, Any] | None = None
    tech_stack: list[str] | None = None
