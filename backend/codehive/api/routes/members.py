"""Workspace membership management endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_current_user, get_db
from codehive.api.schemas.member import MemberAdd, MemberRead, MemberUpdate
from codehive.core.permissions import check_workspace_access
from codehive.db.models import User, WorkspaceMember

router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/members",
    tags=["members"],
)


@router.get("", response_model=list[MemberRead])
async def list_members(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MemberRead]:
    """List all members of a workspace (viewer+ required)."""
    await check_workspace_access(db, current_user.id, workspace_id, "viewer")
    result = await db.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
    )
    members = list(result.scalars().all())
    return [MemberRead.model_validate(m) for m in members]


@router.post("", response_model=MemberRead, status_code=201)
async def add_member(
    workspace_id: uuid.UUID,
    body: MemberAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberRead:
    """Add a member to a workspace (admin+ required)."""
    await check_workspace_access(db, current_user.id, workspace_id, "admin")

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=body.user_id,
        role=body.role,
        created_at=datetime.now(timezone.utc),
    )
    db.add(member)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="User is already a member")
    await db.refresh(member)
    return MemberRead.model_validate(member)


@router.patch("/{user_id}", response_model=MemberRead)
async def update_member_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberRead:
    """Update a member's role (admin+ required, cannot change owner)."""
    await check_workspace_access(db, current_user.id, workspace_id, "admin")

    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot change owner's role")

    member.role = body.role
    await db.commit()
    await db.refresh(member)
    return MemberRead.model_validate(member)


@router.delete("/{user_id}", status_code=204)
async def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a member from a workspace (admin+ required, cannot remove owner)."""
    await check_workspace_access(db, current_user.id, workspace_id, "admin")

    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.role == "owner":
        raise HTTPException(status_code=403, detail="Cannot remove owner")

    await db.delete(member)
    await db.commit()
