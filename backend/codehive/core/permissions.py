"""Permission checks for workspace membership and role hierarchy."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import Project, WorkspaceMember

ROLE_HIERARCHY: dict[str, int] = {
    "owner": 4,
    "admin": 3,
    "member": 2,
    "viewer": 1,
}


async def check_workspace_access(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    required_role: str = "viewer",
) -> WorkspaceMember | None:
    """Verify user has the required role in the workspace.

    Returns the WorkspaceMember row if access is granted.
    Raises HTTPException(403) if denied.

    When ``auth_enabled`` is ``False``, returns ``None`` immediately (bypass).
    """
    from codehive.config import Settings

    if not Settings().auth_enabled:
        return None

    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this workspace",
        )

    user_level = ROLE_HIERARCHY.get(membership.role, 0)
    required_level = ROLE_HIERARCHY.get(required_role, 0)

    if user_level < required_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {required_role} role or higher",
        )

    return membership


async def check_project_access(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    required_role: str = "viewer",
) -> WorkspaceMember | None:
    """Verify user has the required role in the project's workspace.

    Looks up the project's workspace_id, then delegates to check_workspace_access.
    Raises HTTPException(404) if project not found, HTTPException(403) if denied.

    When ``auth_enabled`` is ``False``, returns ``None`` immediately (bypass).
    """
    from codehive.config import Settings

    if not Settings().auth_enabled:
        return None

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return await check_workspace_access(db, user_id, project.workspace_id, required_role)
