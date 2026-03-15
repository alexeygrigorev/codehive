"""CRUD + state transition endpoints for sessions."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.session import SessionCreate, SessionRead, SessionUpdate
from codehive.core.session import (
    InvalidStatusTransitionError,
    IssueNotFoundError,
    ProjectNotFoundError,
    SessionHasDependentsError,
    SessionNotFoundError,
    create_session,
    delete_session,
    get_session,
    list_sessions,
    pause_session,
    resume_session,
    update_session,
)

# Project-scoped routes (create, list)
project_sessions_router = APIRouter(prefix="/api/projects/{project_id}/sessions", tags=["sessions"])

# Flat routes (get, update, delete, pause, resume)
sessions_router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@project_sessions_router.post("", response_model=SessionRead, status_code=201)
async def create_session_endpoint(
    project_id: uuid.UUID,
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    try:
        session = await create_session(
            db,
            project_id=project_id,
            name=body.name,
            engine=body.engine,
            mode=body.mode,
            issue_id=body.issue_id,
            parent_session_id=body.parent_session_id,
            config=body.config,
        )
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except IssueNotFoundError:
        raise HTTPException(status_code=404, detail="Issue not found")
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Parent session not found")
    return SessionRead.model_validate(session)


@project_sessions_router.get("", response_model=list[SessionRead])
async def list_sessions_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[SessionRead]:
    try:
        sessions = await list_sessions(db, project_id)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return [SessionRead.model_validate(s) for s in sessions]


@sessions_router.get("/{session_id}", response_model=SessionRead)
async def get_session_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    session = await get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionRead.model_validate(session)


@sessions_router.patch("/{session_id}", response_model=SessionRead)
async def update_session_endpoint(
    session_id: uuid.UUID,
    body: SessionUpdate,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    fields = body.model_dump(exclude_unset=True)
    try:
        session = await update_session(db, session_id, **fields)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionRead.model_validate(session)


@sessions_router.delete("/{session_id}", status_code=204)
async def delete_session_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_session(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except SessionHasDependentsError:
        raise HTTPException(
            status_code=409,
            detail="Session has child sessions",
        )


@sessions_router.post("/{session_id}/pause", response_model=SessionRead)
async def pause_session_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    try:
        session = await pause_session(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return SessionRead.model_validate(session)


@sessions_router.post("/{session_id}/resume", response_model=SessionRead)
async def resume_session_endpoint(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    try:
        session = await resume_session(db, session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return SessionRead.model_validate(session)
