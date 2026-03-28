"""Orchestrator auto-pipeline API routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.core.issues import create_issue
from codehive.core.orchestrator_service import (
    OrchestratorService,
    get_orchestrator,
    register_orchestrator,
    unregister_orchestrator,
)
from codehive.core.task_queue import create_task
from codehive.db.session import async_session_factory

orchestrator_router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class OrchestratorStartRequest(BaseModel):
    project_id: uuid.UUID
    config: dict[str, Any] | None = None


class OrchestratorStopRequest(BaseModel):
    project_id: uuid.UUID


class OrchestratorStatusRequest(BaseModel):
    project_id: uuid.UUID


class AddTaskRequest(BaseModel):
    project_id: uuid.UUID
    title: str
    description: str | None = None
    acceptance_criteria: str | None = None


class OrchestratorResponse(BaseModel):
    status: str
    project_id: str | None = None
    current_batch: list[str] | None = None
    active_sessions: list[str] | None = None
    flagged_tasks: list[str] | None = None


class AddTaskResponse(BaseModel):
    issue_id: str
    task_id: str
    pipeline_status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@orchestrator_router.post("/start", response_model=OrchestratorResponse)
async def start_orchestrator(
    body: OrchestratorStartRequest,
    db: AsyncSession = Depends(get_db),
) -> OrchestratorResponse:
    """Start the orchestrator for a project."""
    existing = get_orchestrator(body.project_id)
    if existing and existing.running:
        raise HTTPException(status_code=409, detail="Orchestrator already running for this project")

    session_factory = async_session_factory()
    service = OrchestratorService(
        db_session_factory=session_factory,
        project_id=body.project_id,
        config=body.config,
    )

    try:
        register_orchestrator(service)
    except ValueError:
        raise HTTPException(status_code=409, detail="Orchestrator already running for this project")

    await service.start()

    return OrchestratorResponse(
        status="running",
        project_id=str(body.project_id),
    )


@orchestrator_router.post("/stop", response_model=OrchestratorResponse)
async def stop_orchestrator(
    body: OrchestratorStopRequest,
    db: AsyncSession = Depends(get_db),
) -> OrchestratorResponse:
    """Stop the orchestrator for a project. Idempotent."""
    existing = get_orchestrator(body.project_id)
    if existing and existing.running:
        await existing.stop()
        unregister_orchestrator(body.project_id)

    return OrchestratorResponse(
        status="stopped",
        project_id=str(body.project_id),
    )


@orchestrator_router.get("/status", response_model=OrchestratorResponse)
async def orchestrator_status(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OrchestratorResponse:
    """Get the orchestrator status for a project."""
    existing = get_orchestrator(project_id)
    if existing:
        info = existing.get_status()
        return OrchestratorResponse(
            status=info["status"],
            project_id=info["project_id"],
            current_batch=info["current_batch"],
            active_sessions=info["active_sessions"],
            flagged_tasks=info["flagged_tasks"],
        )

    return OrchestratorResponse(
        status="stopped",
        project_id=str(project_id),
    )


@orchestrator_router.post("/add-task", response_model=AddTaskResponse, status_code=201)
async def add_task(
    body: AddTaskRequest,
    db: AsyncSession = Depends(get_db),
) -> AddTaskResponse:
    """Add a task to the pipeline backlog. Creates an issue and a task."""
    from codehive.db.models import Project
    from codehive.db.models import Session as SessionModel
    from sqlalchemy import select

    # Verify project exists
    project = await db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Create the issue
    issue = await create_issue(
        db,
        project_id=body.project_id,
        title=body.title,
        description=body.description,
        acceptance_criteria=body.acceptance_criteria,
    )

    # Find or create an orchestrator session for the project
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.project_id == body.project_id,
            SessionModel.name == f"orchestrator-{body.project_id}",
        )
    )
    orch_session = result.scalar_one_or_none()
    if orch_session is None:
        from codehive.core.session import create_session as create_db_session

        orch_session = await create_db_session(
            db,
            project_id=body.project_id,
            name=f"orchestrator-{body.project_id}",
            engine="claude_code",
            mode="orchestrator",
            issue_id=issue.id,
        )

    # Create the task in backlog
    task = await create_task(
        db,
        session_id=orch_session.id,
        title=body.title,
        instructions=body.description,
        pipeline_status="backlog",
    )

    return AddTaskResponse(
        issue_id=str(issue.id),
        task_id=str(task.id),
        pipeline_status="backlog",
    )
