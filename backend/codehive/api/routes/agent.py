"""Agent API routes -- simple HTTP endpoints for CLI-based agents.

Agents identify themselves via the ``X-Session-Id`` header. The session's
bound task, linked issue, and role are used to infer context automatically.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.core.issues import create_issue_log_entry
from codehive.core.session import get_session
from codehive.core.verdicts import VerdictValue, submit_verdict
from codehive.db.models import Session as SessionModel

agent_router = APIRouter(prefix="/api/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# Dependency: resolve session from X-Session-Id header
# ---------------------------------------------------------------------------


async def get_agent_session(
    x_session_id: uuid.UUID = Header(...),
    db: AsyncSession = Depends(get_db),
) -> tuple[SessionModel, AsyncSession]:
    """Look up the session by ``X-Session-Id`` header.

    Returns a tuple of (session, db) so endpoints have access to both.
    Raises 404 if the session does not exist.
    """
    session = await get_session(db, x_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session, db


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AgentTaskResponse(BaseModel):
    task_id: str
    title: str
    instructions: str | None
    acceptance_criteria: str | None
    pipeline_step: str
    issue_id: str | None
    issue_description: str | None


class AgentLogRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


class AgentVerdictRequest(BaseModel):
    verdict: str
    feedback: str | None = None
    evidence: list[dict] | None = None
    criteria_results: list[dict] | None = None

    @field_validator("verdict")
    @classmethod
    def validate_verdict(cls, v: str) -> str:
        valid = {e.value for e in VerdictValue}
        if v not in valid:
            raise ValueError(f"Invalid verdict '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@agent_router.get("/my-task", response_model=AgentTaskResponse)
async def get_my_task(
    session_and_db: tuple[SessionModel, AsyncSession] = Depends(get_agent_session),
) -> AgentTaskResponse:
    """Return task details for the calling agent's bound task."""
    session, db = session_and_db

    if session.task_id is None:
        raise HTTPException(status_code=404, detail="Session has no bound task")

    # Load the bound task
    await db.refresh(session, attribute_names=["bound_task"])
    task = session.bound_task
    if task is None:
        raise HTTPException(status_code=404, detail="Session has no bound task")

    # Load the linked issue (if any)
    issue_id: str | None = None
    issue_description: str | None = None
    acceptance_criteria: str | None = None

    if session.issue_id is not None:
        await db.refresh(session, attribute_names=["issue"])
        issue = session.issue
        if issue is not None:
            issue_id = str(issue.id)
            issue_description = issue.description
            acceptance_criteria = issue.acceptance_criteria

    return AgentTaskResponse(
        task_id=str(task.id),
        title=task.title,
        instructions=task.instructions,
        acceptance_criteria=acceptance_criteria,
        pipeline_step=task.pipeline_status,
        issue_id=issue_id,
        issue_description=issue_description,
    )


@agent_router.post("/log", status_code=201)
async def post_log(
    body: AgentLogRequest,
    session_and_db: tuple[SessionModel, AsyncSession] = Depends(get_agent_session),
) -> dict:
    """Append a log entry to the session's linked issue."""
    session, db = session_and_db

    if session.issue_id is None:
        raise HTTPException(status_code=404, detail="Session has no linked issue")

    agent_role = session.role or "agent"

    entry = await create_issue_log_entry(
        db,
        issue_id=session.issue_id,
        agent_role=agent_role,
        content=body.content,
    )

    return {"id": str(entry.id), "status": "created"}


@agent_router.post("/verdict")
async def post_verdict(
    body: AgentVerdictRequest,
    session_and_db: tuple[SessionModel, AsyncSession] = Depends(get_agent_session),
) -> dict:
    """Submit a structured verdict for the session's bound task."""
    session, db = session_and_db

    role = session.role or "agent"
    task_id = str(session.task_id) if session.task_id else None

    try:
        event = await submit_verdict(
            db,
            session.id,
            verdict=body.verdict,
            role=role,
            task_id=task_id,
            evidence=body.evidence,
            criteria_results=body.criteria_results,
            feedback=body.feedback,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"id": str(event.id), "status": "created"}
