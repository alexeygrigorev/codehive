"""CRUD endpoints for workspaces."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.project import ProjectRead
from codehive.api.schemas.workspace import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from codehive.core.workspace import (
    WorkspaceDuplicateNameError,
    WorkspaceHasDependentsError,
    WorkspaceNotFoundError,
    create_workspace,
    delete_workspace,
    get_workspace,
    list_workspace_projects,
    list_workspaces,
    update_workspace,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceRead, status_code=201)
async def create_workspace_endpoint(
    body: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
) -> WorkspaceRead:
    try:
        workspace = await create_workspace(
            db,
            name=body.name,
            root_path=body.root_path,
            settings=body.settings,
        )
    except WorkspaceDuplicateNameError:
        raise HTTPException(status_code=409, detail="Workspace name already exists")
    return WorkspaceRead.model_validate(workspace)


@router.get("", response_model=list[WorkspaceRead])
async def list_workspaces_endpoint(
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceRead]:
    workspaces = await list_workspaces(db)
    return [WorkspaceRead.model_validate(w) for w in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace_endpoint(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WorkspaceRead:
    workspace = await get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceRead.model_validate(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
async def update_workspace_endpoint(
    workspace_id: uuid.UUID,
    body: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
) -> WorkspaceRead:
    fields = body.model_dump(exclude_unset=True)
    try:
        workspace = await update_workspace(db, workspace_id, **fields)
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except WorkspaceDuplicateNameError:
        raise HTTPException(status_code=409, detail="Workspace name already exists")
    return WorkspaceRead.model_validate(workspace)


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace_endpoint(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_workspace(db, workspace_id)
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    except WorkspaceHasDependentsError:
        raise HTTPException(
            status_code=409,
            detail="Workspace has associated projects",
        )


@router.get("/{workspace_id}/projects", response_model=list[ProjectRead])
async def list_workspace_projects_endpoint(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ProjectRead]:
    try:
        projects = await list_workspace_projects(db, workspace_id)
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return [ProjectRead.model_validate(p) for p in projects]
