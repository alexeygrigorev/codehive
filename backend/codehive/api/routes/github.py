"""API endpoints for GitHub integration: configure, import, status."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.github import (
    GitHubConfigureRequest,
    GitHubConfigureResponse,
    GitHubImportRequest,
    GitHubImportResponse,
    GitHubStatusResponse,
)
from codehive.db.models import Project
from codehive.integrations.github.importer import import_issues

github_router = APIRouter(
    prefix="/api/projects/{project_id}/github",
    tags=["github"],
)


def _mask_token(token: str) -> str:
    """Mask a token, showing only first 4 chars."""
    if len(token) <= 4:
        return token[:1] + "***"
    return token[:4] + "***"


async def _get_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    """Get a project or raise 404."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@github_router.post("/configure", response_model=GitHubConfigureResponse)
async def configure_github(
    project_id: uuid.UUID,
    body: GitHubConfigureRequest,
    db: AsyncSession = Depends(get_db),
) -> GitHubConfigureResponse:
    """Save GitHub repo config for a project."""
    project = await _get_project(db, project_id)

    config = {
        "owner": body.owner,
        "repo": body.repo,
        "token": body.token,
        "last_import_at": None,
        "trigger_mode": body.trigger_mode,
    }

    if body.webhook_secret is not None:
        config["webhook_secret"] = body.webhook_secret

    project.github_config = config

    await db.commit()
    await db.refresh(project)

    return GitHubConfigureResponse(
        owner=body.owner,
        repo=body.repo,
        token_masked=_mask_token(body.token),
    )


@github_router.get("/status", response_model=GitHubStatusResponse)
async def github_status(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> GitHubStatusResponse:
    """Return the saved GitHub config (token masked) and last import timestamp."""
    project = await _get_project(db, project_id)

    config = project.github_config

    if not config:
        return GitHubStatusResponse(configured=False)

    return GitHubStatusResponse(
        configured=True,
        owner=config["owner"],
        repo=config["repo"],
        token_masked=_mask_token(config["token"]),
        last_import_at=config.get("last_import_at"),
        trigger_mode=config.get("trigger_mode", "manual"),
    )


@github_router.post("/import", response_model=GitHubImportResponse)
async def trigger_import(
    project_id: uuid.UUID,
    body: GitHubImportRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> GitHubImportResponse:
    """Trigger a manual import of GitHub issues."""
    project = await _get_project(db, project_id)

    config = project.github_config

    if not config:
        raise HTTPException(
            status_code=400,
            detail="GitHub integration is not configured for this project",
        )

    since = body.since if body else None

    result = await import_issues(
        db,
        project_id=project.id,
        owner=config["owner"],
        repo=config["repo"],
        token=config["token"],
        since=since,
    )

    # Update last_import_at
    config = dict(config)
    config["last_import_at"] = datetime.now(timezone.utc).isoformat()
    project.github_config = config
    await db.commit()

    return GitHubImportResponse(
        created=result.created,
        updated=result.updated,
        errors=result.errors,
    )
