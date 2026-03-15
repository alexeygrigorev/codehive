"""CRUD endpoints for projects."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from codehive.core.project import (
    InvalidArchetypeError,
    ProjectHasDependentsError,
    ProjectNotFoundError,
    WorkspaceNotFoundError,
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project_endpoint(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    try:
        project = await create_project(
            db,
            workspace_id=body.workspace_id,
            name=body.name,
            path=body.path,
            description=body.description,
            archetype=body.archetype,
        )
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except InvalidArchetypeError:
        raise HTTPException(status_code=400, detail=f"Invalid archetype: '{body.archetype}'")
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
async def list_projects_endpoint(
    db: AsyncSession = Depends(get_db),
) -> list[ProjectRead]:
    projects = await list_projects(db)
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
