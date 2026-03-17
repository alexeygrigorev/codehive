"""CRUD endpoints for workspaces."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_current_user, get_db
from codehive.api.schemas.project import ProjectRead
from codehive.api.schemas.workspace import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from codehive.core.permissions import check_workspace_access
from codehive.core.workspace import (
    WorkspaceDuplicateNameError,
    WorkspaceHasDependentsError,
    WorkspaceNotFoundError,
    create_workspace,
    delete_workspace,
    get_workspace,
    list_workspace_projects,
    update_workspace,
)
from codehive.db.models import User, WorkspaceMember

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceRead, status_code=201)
async def create_workspace_endpoint(
    body: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
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

    # Auto-assign creator as owner
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role="owner",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(member)
    await db.commit()

    return WorkspaceRead.model_validate(workspace)


@router.get("", response_model=list[WorkspaceRead])
async def list_workspaces_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceRead]:
    # Return only workspaces where user is a member
    result = await db.execute(
        select(WorkspaceMember.workspace_id).where(
            WorkspaceMember.user_id == current_user.id,
        )
    )
    ws_ids = [row[0] for row in result.all()]
    if not ws_ids:
        return []

    from codehive.db.models import Workspace

    result = await db.execute(select(Workspace).where(Workspace.id.in_(ws_ids)))
    workspaces = list(result.scalars().all())
    return [WorkspaceRead.model_validate(w) for w in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace_endpoint(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceRead:
    await check_workspace_access(db, current_user.id, workspace_id, "viewer")
    workspace = await get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceRead.model_validate(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
async def update_workspace_endpoint(
    workspace_id: uuid.UUID,
    body: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceRead:
    await check_workspace_access(db, current_user.id, workspace_id, "viewer")
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await check_workspace_access(db, current_user.id, workspace_id, "owner")
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectRead]:
    await check_workspace_access(db, current_user.id, workspace_id, "viewer")
    try:
        projects = await list_workspace_projects(db, workspace_id)
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return [ProjectRead.model_validate(p) for p in projects]
