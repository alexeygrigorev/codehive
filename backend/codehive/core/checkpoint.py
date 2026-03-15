"""Checkpoint business logic (create, list, rollback)."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import Checkpoint
from codehive.db.models import Session as SessionModel
from codehive.execution.git_ops import GitOps

logger = logging.getLogger(__name__)


class SessionNotFoundError(Exception):
    """Raised when a session is not found by ID."""


class CheckpointNotFoundError(Exception):
    """Raised when a checkpoint is not found by ID."""


def _snapshot_session_state(session: SessionModel, *, label: str | None = None) -> dict:
    """Build a JSONB-compatible dict from the session's current state."""
    state: dict = {
        "status": session.status,
        "mode": session.mode,
        "config": session.config,
    }
    if label is not None:
        state["label"] = label
    return state


async def create_checkpoint(
    db: AsyncSession,
    git_ops: GitOps,
    *,
    session_id: uuid.UUID,
    label: str | None = None,
) -> Checkpoint:
    """Create a checkpoint: commit current git state and snapshot session state.

    Args:
        db: Async database session.
        git_ops: GitOps instance for the project repo.
        session_id: The session to checkpoint.
        label: Optional human-readable label for the checkpoint.

    Returns:
        The newly created Checkpoint row.

    Raises:
        SessionNotFoundError: If the session does not exist.
    """
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    commit_message = f"checkpoint: {label}" if label else "checkpoint"
    sha = await git_ops.commit(commit_message)

    state = _snapshot_session_state(session, label=label)
    checkpoint = Checkpoint(
        session_id=session_id,
        git_ref=sha,
        state=state,
        created_at=datetime.now(timezone.utc),
    )
    db.add(checkpoint)
    await db.commit()
    await db.refresh(checkpoint)
    return checkpoint


async def list_checkpoints(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list[Checkpoint]:
    """Return checkpoints for a session ordered by created_at descending.

    Raises:
        SessionNotFoundError: If the session does not exist.
    """
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    result = await db.execute(
        select(Checkpoint)
        .where(Checkpoint.session_id == session_id)
        .order_by(Checkpoint.created_at.desc())
    )
    return list(result.scalars().all())


async def rollback_checkpoint(
    db: AsyncSession,
    git_ops: GitOps,
    *,
    checkpoint_id: uuid.UUID,
) -> SessionModel:
    """Rollback to a checkpoint: restore git state and session state.

    Args:
        db: Async database session.
        git_ops: GitOps instance for the project repo.
        checkpoint_id: The checkpoint to rollback to.

    Returns:
        The updated Session model with restored state.

    Raises:
        CheckpointNotFoundError: If the checkpoint does not exist.
    """
    checkpoint = await db.get(Checkpoint, checkpoint_id)
    if checkpoint is None:
        raise CheckpointNotFoundError(f"Checkpoint {checkpoint_id} not found")

    # Restore git state
    await git_ops.checkout(checkpoint.git_ref)

    # Restore session state from checkpoint
    session = await db.get(SessionModel, checkpoint.session_id)
    state = checkpoint.state
    if "status" in state:
        session.status = state["status"]
    if "mode" in state:
        session.mode = state["mode"]
    if "config" in state:
        session.config = state["config"]

    await db.commit()
    await db.refresh(session)
    return session
