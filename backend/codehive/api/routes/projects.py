"""CRUD endpoints for projects."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from codehive.core.project import (
    InvalidArchetypeError,
    ProjectHasDependentsError,
    ProjectNotFoundError,
    create_project,
    delete_project,
    get_or_create_project_by_path,
    get_project,
    get_project_by_path,
    update_project,
)
from codehive.db.models import Project

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project_endpoint(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    try:
        project = await create_project(
            db,
            name=body.name,
            path=body.path,
            description=body.description,
            archetype=body.archetype,
        )
    except InvalidArchetypeError:
        raise HTTPException(status_code=400, detail=f"Invalid archetype: '{body.archetype}'")
    return ProjectRead.model_validate(project)


@router.get("/by-path", response_model=ProjectRead)
async def get_project_by_path_endpoint(
    path: str = Query(..., description="Absolute filesystem path"),
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    """Look up a project by its filesystem path. Returns 404 if not found."""
    project = await get_project_by_path(db, path)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)


class ProjectByPathRequest(BaseModel):
    """Request body for POST /api/projects/by-path."""

    path: str


@router.post("/by-path", response_model=ProjectRead)
async def create_project_by_path_endpoint(
    body: ProjectByPathRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    """Get or create a project by filesystem path."""
    project, created = await get_or_create_project_by_path(db, body.path)
    response.status_code = 201 if created else 200
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
async def list_projects_endpoint(
    db: AsyncSession = Depends(get_db),
) -> list[ProjectRead]:
    result = await db.execute(select(Project))
    projects = list(result.scalars().all())
    return [ProjectRead.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    project = await get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project_endpoint(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    fields = body.model_dump(exclude_unset=True)
    try:
        project = await update_project(db, project_id, **fields)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_project(db, project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except ProjectHasDependentsError:
        raise HTTPException(
            status_code=409,
            detail="Project has associated sessions or issues",
        )
