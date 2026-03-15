"""Pydantic schemas for knowledge and charter endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KnowledgeUpdate(BaseModel):
    """Request body for PATCH /api/projects/{project_id}/knowledge.

    Accepts any dict of knowledge sections. Keys are merged into
    existing knowledge without destroying unrelated keys.
    Extra fields are allowed so the schema can evolve over time.
    """

    model_config = {"extra": "allow"}

    tech_stack: dict[str, Any] | None = None
    architecture: dict[str, Any] | None = None
    conventions: dict[str, Any] | None = None
    decisions: list[dict[str, Any]] | None = None
    open_decisions: list[dict[str, Any]] | None = None
    charter: dict[str, Any] | None = None


class KnowledgeResponse(BaseModel):
    """Response schema for GET/PATCH knowledge endpoints.

    Returns the full knowledge dict. Extra fields are preserved.
    """

    model_config = {"extra": "allow"}

    tech_stack: dict[str, Any] | None = None
    architecture: dict[str, Any] | None = None
    conventions: dict[str, Any] | None = None
    decisions: list[dict[str, Any]] | None = None
    open_decisions: list[dict[str, Any]] | None = None
    charter: dict[str, Any] | None = None


class CharterDocument(BaseModel):
    """Schema for the agent charter sub-document.

    Extra fields are allowed so the charter can evolve.
    """

    model_config = {"extra": "allow"}

    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    tech_stack_rules: list[str] = Field(default_factory=list)
    coding_rules: list[str] = Field(default_factory=list)
    decision_policies: list[str] = Field(default_factory=list)
