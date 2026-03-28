"""CRUD + status transition + reorder + pipeline endpoints for tasks."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.task import (
    PipelineTransitionRequest,
    TaskCreate,
    TaskPipelineLogRead,
    TaskRead,
    TaskReorderItem,
    TaskStatusTransition,
    TaskUpdate,
)
from codehive.core.task_queue import (
    InvalidDependencyError,
    InvalidPipelineTransitionError,
    InvalidStatusTransitionError,
    RoleNotAllowedError,
    SessionNotFoundError,
    TaskNotFoundError,
    create_task,
    delete_task,
    get_next_task,
    get_pipeline_log,
    get_task,
    list_tasks,
    pipeline_transition,
    reorder_tasks,
    transition_task,
    update_task,
)

# Session-scoped routes (create, list, next, reorder)
session_tasks_router = APIRouter(prefix="/api/sessions/{session_id}/tasks", tags=["tasks"])

# Flat routes (get, update, delete, transition, pipeline)
tasks_router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@session_tasks_router.post("", response_model=TaskRead, status_code=201)
async def create_task_endpoint(
    session_id: uuid.UUID,
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    try:
        task = await create_task(
            db,
            session_id=session_id,
            title=body.title,
            instructions=body.instructions,
            priority=body.priority,
            depends_on=body.depends_on,
            mode=body.mode,
            created_by=body.created_by,
            pipeline_status=body.pipeline_status,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="Dependency task not found")
    except InvalidDependencyError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return TaskRead.model_validate(task)


@session_tasks_router.get("", response_model=list[TaskRead])
async def list_tasks_endpoint(
    session_id: uuid.UUID,
    pipeline_status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[TaskRead]:
    try:
        tasks = await list_tasks(db, session_id, pipeline_status=pipeline_status)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    return [TaskRead.model_validate(t) for t in tasks]


@session_tasks_router.get("/next", response_model=None)
async def get_next_task_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TaskRead | Response:
    try:
        task = await get_next_task(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    if task is None:
        return Response(status_code=204)
    return TaskRead.model_validate(task)


@session_tasks_router.post("/reorder", response_model=list[TaskRead])
async def reorder_tasks_endpoint(
    session_id: uuid.UUID,
    body: list[TaskReorderItem],
    db: AsyncSession = Depends(get_db),
) -> list[TaskRead]:
    try:
        tasks = await reorder_tasks(
            db,
            session_id,
            [{"id": item.id, "priority": item.priority} for item in body],
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except InvalidDependencyError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return [TaskRead.model_validate(t) for t in tasks]


@tasks_router.get("/{task_id}", response_model=TaskRead)
async def get_task_endpoint(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    task = await get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskRead.model_validate(task)


@tasks_router.patch("/{task_id}", response_model=TaskRead)
async def update_task_endpoint(
    task_id: uuid.UUID,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    fields = body.model_dump(exclude_unset=True)
    try:
        task = await update_task(db, task_id, **fields)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except InvalidDependencyError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return TaskRead.model_validate(task)


@tasks_router.delete("/{task_id}", status_code=204)
async def delete_task_endpoint(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_task(db, task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")


@tasks_router.post("/{task_id}/transition", response_model=TaskRead)
async def transition_task_endpoint(
    task_id: uuid.UUID,
    body: TaskStatusTransition,
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    try:
        task = await transition_task(db, task_id, body.status)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return TaskRead.model_validate(task)


@tasks_router.post("/{task_id}/pipeline-transition", response_model=TaskRead)
async def pipeline_transition_endpoint(
    task_id: uuid.UUID,
    body: PipelineTransitionRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    try:
        task = await pipeline_transition(
            db,
            task_id,
            body.status,
            actor=body.actor,
            actor_session_id=body.actor_session_id,
        )
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    except InvalidPipelineTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RoleNotAllowedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Actor session not found")
    return TaskRead.model_validate(task)


@tasks_router.get("/{task_id}/pipeline-log", response_model=list[TaskPipelineLogRead])
async def get_pipeline_log_endpoint(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[TaskPipelineLogRead]:
    try:
        logs = await get_pipeline_log(db, task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
    return [TaskPipelineLogRead.model_validate(entry) for entry in logs]
