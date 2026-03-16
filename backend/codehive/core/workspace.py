"""Workspace business logic (DB queries)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import Project, Workspace


class WorkspaceNotFoundError(Exception):
    """Raised when a workspace is not found by ID."""


class WorkspaceHasDependentsError(Exception):
    """Raised when a workspace cannot be deleted because it has associated projects."""


class WorkspaceDuplicateNameError(Exception):
    """Raised when a workspace name already exists."""


async def create_workspace(
    session: AsyncSession,
    *,
    name: str,
    root_path: str,
    settings: dict | None = None,
) -> Workspace:
    """Create a new workspace. Raises WorkspaceDuplicateNameError if name is taken."""
    workspace = Workspace(
        name=name,
        root_path=root_path,
        settings=settings if settings is not None else {},
        created_at=datetime.now(timezone.utc),
    )
    session.add(workspace)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise WorkspaceDuplicateNameError(f"Workspace with name '{name}' already exists")
    await session.refresh(workspace)
    return workspace


async def list_workspaces(session: AsyncSession) -> list[Workspace]:
    """Return all workspaces."""
    result = await session.execute(select(Workspace))
    return list(result.scalars().all())


async def get_workspace(session: AsyncSession, workspace_id: uuid.UUID) -> Workspace | None:
    """Return a workspace by ID, or None if not found."""
    return await session.get(Workspace, workspace_id)


async def update_workspace(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    **fields: object,
) -> Workspace:
    """Update specific fields on a workspace. Raises WorkspaceNotFoundError if not found."""
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(f"Workspace {workspace_id} not found")

    for key, value in fields.items():
        setattr(workspace, key, value)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise WorkspaceDuplicateNameError(
            f"Workspace with name '{fields.get('name')}' already exists"
        )
    await session.refresh(workspace)
    return workspace


async def delete_workspace(session: AsyncSession, workspace_id: uuid.UUID) -> None:
    """Delete a workspace. Raises WorkspaceNotFoundError if not found.

    Raises WorkspaceHasDependentsError if the workspace has associated projects.
    """
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(f"Workspace {workspace_id} not found")

    # Check for dependent projects
    await session.refresh(workspace, attribute_names=["projects"])
    if workspace.projects:
        raise WorkspaceHasDependentsError(f"Workspace {workspace_id} has associated projects")

    # Delete workspace members first
    await session.refresh(workspace, attribute_names=["members"])
    for member in workspace.members:
        await session.delete(member)

    await session.delete(workspace)
    await session.commit()


async def list_workspace_projects(session: AsyncSession, workspace_id: uuid.UUID) -> list[Project]:
    """List projects belonging to a workspace. Raises WorkspaceNotFoundError if not found."""
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(f"Workspace {workspace_id} not found")

    result = await session.execute(select(Project).where(Project.workspace_id == workspace_id))
    return list(result.scalars().all())
