"""Remote target CRUD operations."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import RemoteTarget


class RemoteTargetNotFoundError(Exception):
    """Raised when a remote target is not found by ID."""


class RemoteTargetHasActiveConnectionError(Exception):
    """Raised when trying to delete a target that has an active connection."""


class RemoteTargetValidationError(Exception):
    """Raised when required fields are missing."""


async def create_remote_target(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    label: str,
    host: str,
    username: str,
    port: int = 22,
    key_path: str | None = None,
    known_hosts_policy: str = "auto",
) -> RemoteTarget:
    """Create a new remote target.

    Args:
        session: Database session.
        workspace_id: UUID of the workspace.
        label: Human-readable label.
        host: Hostname or IP address.
        username: SSH username.
        port: SSH port (default 22).
        key_path: Path to SSH private key.
        known_hosts_policy: Known hosts policy (auto, ignore).

    Returns:
        The created RemoteTarget.

    Raises:
        RemoteTargetValidationError: If required fields are missing.
    """
    if not host or not host.strip():
        raise RemoteTargetValidationError("host is required")
    if not username or not username.strip():
        raise RemoteTargetValidationError("username is required")

    target = RemoteTarget(
        workspace_id=workspace_id,
        label=label,
        host=host,
        port=port,
        username=username,
        key_path=key_path,
        known_hosts_policy=known_hosts_policy,
        created_at=datetime.now(timezone.utc),
    )
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return target


async def list_remote_targets(
    session: AsyncSession,
    workspace_id: uuid.UUID | None = None,
) -> list[RemoteTarget]:
    """List remote targets, optionally filtered by workspace.

    Args:
        session: Database session.
        workspace_id: Optional workspace UUID to filter by.

    Returns:
        List of RemoteTarget objects.
    """
    stmt = select(RemoteTarget)
    if workspace_id is not None:
        stmt = stmt.where(RemoteTarget.workspace_id == workspace_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_remote_target(
    session: AsyncSession,
    target_id: uuid.UUID,
) -> RemoteTarget | None:
    """Get a remote target by ID.

    Args:
        session: Database session.
        target_id: UUID of the target.

    Returns:
        The RemoteTarget or None if not found.
    """
    return await session.get(RemoteTarget, target_id)


async def update_remote_target(
    session: AsyncSession,
    target_id: uuid.UUID,
    **fields: object,
) -> RemoteTarget:
    """Update specific fields on a remote target.

    Args:
        session: Database session.
        target_id: UUID of the target.
        **fields: Fields to update.

    Returns:
        The updated RemoteTarget.

    Raises:
        RemoteTargetNotFoundError: If target is not found.
    """
    target = await session.get(RemoteTarget, target_id)
    if target is None:
        raise RemoteTargetNotFoundError(f"Remote target {target_id} not found")

    for key, value in fields.items():
        setattr(target, key, value)

    await session.commit()
    await session.refresh(target)
    return target


async def delete_remote_target(
    session: AsyncSession,
    target_id: uuid.UUID,
    active_connection_ids: set[uuid.UUID] | None = None,
) -> None:
    """Delete a remote target.

    Args:
        session: Database session.
        target_id: UUID of the target.
        active_connection_ids: Set of target IDs with active SSH connections.

    Raises:
        RemoteTargetNotFoundError: If target is not found.
        RemoteTargetHasActiveConnectionError: If target has an active connection.
    """
    target = await session.get(RemoteTarget, target_id)
    if target is None:
        raise RemoteTargetNotFoundError(f"Remote target {target_id} not found")

    if active_connection_ids and target_id in active_connection_ids:
        raise RemoteTargetHasActiveConnectionError(
            f"Remote target {target_id} has an active connection"
        )

    await session.delete(target)
    await session.commit()
