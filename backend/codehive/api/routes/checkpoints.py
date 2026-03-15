"""Checkpoint endpoints: list, create, rollback."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.checkpoint import CheckpointCreate, CheckpointRead
from codehive.api.schemas.session import SessionRead
from codehive.core.checkpoint import (
    CheckpointNotFoundError,
    SessionNotFoundError,
    create_checkpoint,
    list_checkpoints,
    rollback_checkpoint,
)
from codehive.execution.git_ops import GitOps

# Session-scoped routes (list, create)
session_checkpoints_router = APIRouter(
    prefix="/api/sessions/{session_id}/checkpoints", tags=["checkpoints"]
)

# Flat routes (rollback)
checkpoints_router = APIRouter(prefix="/api/checkpoints", tags=["checkpoints"])


def _get_git_ops(project_root: str = "/tmp") -> GitOps:
    """Construct a GitOps instance. In production, resolve from session config."""
    return GitOps(repo_path=Path(project_root))


@session_checkpoints_router.post("", response_model=CheckpointRead, status_code=201)
async def create_checkpoint_endpoint(
    session_id: uuid.UUID,
    body: CheckpointCreate,
    db: AsyncSession = Depends(get_db),
) -> CheckpointRead:
    try:
        # Resolve project root from session config
        from codehive.db.models import Session as SessionModel

        session = await db.get(SessionModel, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        project_root = session.config.get("project_root", "/tmp")
        git_ops = _get_git_ops(project_root)

        checkpoint = await create_checkpoint(
            db,
            git_ops,
            session_id=session_id,
            label=body.label,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    return CheckpointRead.model_validate(checkpoint)


@session_checkpoints_router.get("", response_model=list[CheckpointRead])
async def list_checkpoints_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[CheckpointRead]:
    try:
        checkpoints = await list_checkpoints(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    return [CheckpointRead.model_validate(c) for c in checkpoints]


@checkpoints_router.post("/{checkpoint_id}/rollback", response_model=SessionRead)
async def rollback_checkpoint_endpoint(
    checkpoint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    try:
        # Need to resolve git_ops from checkpoint's session config
        from codehive.db.models import Checkpoint as CheckpointModel
        from codehive.db.models import Session as SessionModel

        checkpoint = await db.get(CheckpointModel, checkpoint_id)
        if checkpoint is None:
            raise HTTPException(status_code=404, detail="Checkpoint not found")

        session = await db.get(SessionModel, checkpoint.session_id)
        project_root = session.config.get("project_root", "/tmp") if session else "/tmp"
        git_ops = _get_git_ops(project_root)

        session = await rollback_checkpoint(
            db,
            git_ops,
            checkpoint_id=checkpoint_id,
        )
    except CheckpointNotFoundError:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return SessionRead.model_validate(session)
