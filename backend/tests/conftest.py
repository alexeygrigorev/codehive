"""Shared test helpers for workspace membership."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import User, WorkspaceMember


async def ensure_workspace_membership(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_email: str = "test@test.com",
    role: str = "owner",
) -> None:
    """Create a workspace membership for the first matching user.

    This is a test helper to ensure API tests work with permission checks.
    """
    result = await db.execute(select(User).where(User.email == user_email))
    user = result.scalar_one_or_none()
    if user is None:
        return

    # Check if membership already exists
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if result.scalar_one_or_none() is not None:
        return

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user.id,
        role=role,
        created_at=datetime.now(timezone.utc),
    )
    db.add(member)
    await db.commit()
