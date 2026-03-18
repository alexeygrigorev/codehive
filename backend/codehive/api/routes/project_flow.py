"""API routes for the guided project creation flow."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.project_flow import (
    CreatedSession,
    ProjectFlowFinalizeResult,
    ProjectFlowRespond,
    ProjectFlowRespondResult,
    ProjectFlowStart,
    ProjectFlowStartResult,
)
from codehive.core.project_flow import (
    FlowAlreadyFinalizedError,
    FlowNotFoundError,
    finalize_flow,
    respond_to_flow,
    start_flow,
)

router = APIRouter(prefix="/api/project-flow", tags=["project-flow"])


@router.post("/start", response_model=ProjectFlowStartResult)
async def start_flow_endpoint(
    body: ProjectFlowStart,
    db: AsyncSession = Depends(get_db),
) -> ProjectFlowStartResult:
    """Start a new project creation flow."""
    flow_id, session_id, questions = await start_flow(
        db,
        flow_type=body.flow_type,
        initial_input=body.initial_input,
    )

    return ProjectFlowStartResult(
        flow_id=flow_id,
        session_id=session_id,
        first_questions=questions,
    )


@router.post("/{flow_id}/respond", response_model=ProjectFlowRespondResult)
async def respond_flow_endpoint(
    flow_id: uuid.UUID,
    body: ProjectFlowRespond,
) -> ProjectFlowRespondResult:
    """Respond to questions in a project flow."""
    try:
        next_questions, brief = await respond_to_flow(
            flow_id,
            answers=[a.model_dump() for a in body.answers],
        )
    except FlowNotFoundError:
        raise HTTPException(status_code=404, detail="Flow not found")

    return ProjectFlowRespondResult(
        next_questions=next_questions,
        brief=brief,
    )


@router.post("/{flow_id}/finalize", response_model=ProjectFlowFinalizeResult)
async def finalize_flow_endpoint(
    flow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectFlowFinalizeResult:
    """Finalize a flow: create project, knowledge, and sessions."""
    try:
        project_id, sessions = await finalize_flow(db, flow_id)
    except FlowNotFoundError:
        raise HTTPException(status_code=404, detail="Flow not found")
    except FlowAlreadyFinalizedError:
        raise HTTPException(status_code=409, detail="Flow already finalized")

    return ProjectFlowFinalizeResult(
        project_id=project_id,
        sessions=[CreatedSession(**s) for s in sessions],
    )
