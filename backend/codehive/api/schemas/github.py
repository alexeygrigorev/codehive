"""Pydantic schemas for GitHub integration endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GitHubConfigureRequest(BaseModel):
    """Request body for POST /api/projects/{project_id}/github/configure."""

    owner: str = Field(..., min_length=1)
    repo: str = Field(..., min_length=1)
    token: str = Field(..., min_length=1)
    webhook_secret: str | None = None
    trigger_mode: str = "manual"
    sync_labels: list[str] = Field(default_factory=list)


class GitHubConfigureResponse(BaseModel):
    """Response for configure endpoint -- token is masked."""

    owner: str
    repo: str
    token_masked: str


class GitHubImportRequest(BaseModel):
    """Optional request body for POST /api/projects/{project_id}/github/import."""

    since: str | None = None


class GitHubImportResponse(BaseModel):
    """Response for import endpoint."""

    created: int
    updated: int
    errors: list[str]


class GitHubStatusResponse(BaseModel):
    """Response for GET /api/projects/{project_id}/github/status."""

    configured: bool
    owner: str | None = None
    repo: str | None = None
    token_masked: str | None = None
    last_import_at: str | None = None
    trigger_mode: str | None = None
    sync_labels: list[str] = Field(default_factory=list)
