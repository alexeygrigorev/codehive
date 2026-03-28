"""Orchestrator auto-pipeline API routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.core.backlog_service import (
    ProjectNotFoundForBacklogError,
    create_backlog_task,
)
from codehive.core.orchestrator_service import (
    OrchestratorService,
    get_orchestrator,
    register_orchestrator,
    unregister_orchestrator,
)
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
    try:
        result = await create_backlog_task(
            db,
            project_id=body.project_id,
            title=body.title,
            description=body.description,
            acceptance_criteria=body.acceptance_criteria,
        )
    except ProjectNotFoundForBacklogError:
        raise HTTPException(status_code=404, detail="Project not found")

    return AddTaskResponse(
        issue_id=str(result.issue_id),
        task_id=str(result.task_id),
        pipeline_status=result.pipeline_status,
    )
