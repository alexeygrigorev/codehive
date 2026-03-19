"""API endpoints for GitHub repo listing and cloning via ``gh`` CLI."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.core.project import create_project
from codehive.integrations.github.repos import (
    check_gh_status,
    clone_repo,
    list_repos,
)

github_repos_router = APIRouter(prefix="/api/github", tags=["github-repos"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GhStatusResponse(BaseModel):
    available: bool
    authenticated: bool
    username: str | None = None
    error: str | None = None


class RepoItem(BaseModel):
    name: str
    full_name: str
    description: str | None = None
    language: str | None = None
    updated_at: str | None = None
    is_private: bool = False
    clone_url: str


class RepoListResponse(BaseModel):
    repos: list[RepoItem]
    owner: str | None = None
    total: int


class CloneRequest(BaseModel):
    repo_url: str
    destination: str
    project_name: str


class CloneResponse(BaseModel):
    project_id: str
    project_name: str
    path: str
    cloned: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@github_repos_router.get("/status", response_model=GhStatusResponse)
async def gh_status() -> GhStatusResponse:
    """Check whether ``gh`` CLI is available and authenticated."""
    result = await check_gh_status()
    return GhStatusResponse(
        available=result.available,
        authenticated=result.authenticated,
        username=result.username,
        error=result.error,
    )


@github_repos_router.get("/repos", response_model=RepoListResponse)
async def gh_repos(
    owner: str | None = Query(None, description="GitHub username or org name"),
    search: str | None = Query(None, description="Filter repos by name"),
    limit: int = Query(100, ge=1, le=1000, description="Max repos to fetch"),
) -> RepoListResponse:
    """List GitHub repositories for the authenticated user or a given owner."""
    try:
        result = await list_repos(owner=owner, search=search, limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return RepoListResponse(
        repos=[
            RepoItem(
                name=r.name,
                full_name=r.full_name,
                description=r.description,
                language=r.language,
                updated_at=r.updated_at,
                is_private=r.is_private,
                clone_url=r.clone_url,
            )
            for r in result.repos
        ],
        owner=result.owner,
        total=result.total,
    )


@github_repos_router.post("/clone", response_model=CloneResponse)
async def gh_clone(
    body: CloneRequest,
    db: AsyncSession = Depends(get_db),
) -> CloneResponse:
    """Clone a GitHub repo and create a project."""
    try:
        cloned_path = await clone_repo(
            repo_url=body.repo_url,
            destination=body.destination,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Create the project record
    project = await create_project(
        db,
        name=body.project_name,
        path=cloned_path,
    )

    return CloneResponse(
        project_id=str(project.id),
        project_name=project.name,
        path=cloned_path,
        cloned=True,
    )
