"""CRUD endpoints for issues."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.issue import (
    IssueCreate,
    IssueLogEntryCreate,
    IssueLogEntryRead,
    IssueRead,
    IssueReadWithSessions,
    IssueUpdate,
)
from codehive.api.schemas.session import SessionRead
from codehive.core.issues import (
    InvalidStatusTransitionError,
    IssueHasLinkedSessionsError,
    IssueNotFoundError,
    ProjectNotFoundError,
    SessionNotFoundError,
    create_issue,
    create_issue_log_entry,
    delete_issue,
    get_issue,
    link_session_to_issue,
    list_issue_log_entries,
    list_issues,
    update_issue,
)

# Project-scoped routes (create, list)
project_issues_router = APIRouter(prefix="/api/projects/{project_id}/issues", tags=["issues"])

# Flat routes (get, update, delete, link-session, logs)
issues_router = APIRouter(prefix="/api/issues", tags=["issues"])


@project_issues_router.post("", response_model=IssueRead, status_code=201)
async def create_issue_endpoint(
    project_id: uuid.UUID,
    body: IssueCreate,
    db: AsyncSession = Depends(get_db),
) -> IssueRead:
    try:
        issue = await create_issue(
            db,
            project_id=project_id,
            title=body.title,
            description=body.description,
            acceptance_criteria=body.acceptance_criteria,
            assigned_agent=body.assigned_agent,
            priority=body.priority,
        )
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return IssueRead.model_validate(issue)


@project_issues_router.get("", response_model=list[IssueRead])
async def list_issues_endpoint(
    project_id: uuid.UUID,
    status: str | None = Query(default=None),
    assigned_agent: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[IssueRead]:
    try:
        issues = await list_issues(db, project_id, status=status, assigned_agent=assigned_agent)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    return [IssueRead.model_validate(i) for i in issues]


@issues_router.get("/{issue_id}", response_model=IssueReadWithSessions)
async def get_issue_endpoint(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> IssueReadWithSessions:
    issue = await get_issue(db, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return IssueReadWithSessions.model_validate(issue)


@issues_router.patch("/{issue_id}", response_model=IssueRead)
async def update_issue_endpoint(
    issue_id: uuid.UUID,
    body: IssueUpdate,
    db: AsyncSession = Depends(get_db),
) -> IssueRead:
    fields = body.model_dump(exclude_unset=True)
    try:
        issue = await update_issue(db, issue_id, **fields)
    except IssueNotFoundError:
        raise HTTPException(status_code=404, detail="Issue not found")
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return IssueRead.model_validate(issue)


@issues_router.delete("/{issue_id}", status_code=204)
async def delete_issue_endpoint(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_issue(db, issue_id)
    except IssueNotFoundError:
        raise HTTPException(status_code=404, detail="Issue not found")
    except IssueHasLinkedSessionsError:
        raise HTTPException(
            status_code=409,
            detail="Issue has linked sessions",
        )


@issues_router.post("/{issue_id}/link-session/{session_id}", response_model=SessionRead)
async def link_session_endpoint(
    issue_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    try:
        session = await link_session_to_issue(db, issue_id, session_id)
    except IssueNotFoundError:
        raise HTTPException(status_code=404, detail="Issue not found")
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionRead.model_validate(session)


# ---------------------------------------------------------------------------
# Issue log entry endpoints
# ---------------------------------------------------------------------------


@issues_router.post("/{issue_id}/logs", response_model=IssueLogEntryRead, status_code=201)
async def create_log_entry_endpoint(
    issue_id: uuid.UUID,
    body: IssueLogEntryCreate,
    db: AsyncSession = Depends(get_db),
) -> IssueLogEntryRead:
    try:
        entry = await create_issue_log_entry(
            db,
            issue_id=issue_id,
            agent_role=body.agent_role,
            content=body.content,
        )
    except IssueNotFoundError:
        raise HTTPException(status_code=404, detail="Issue not found")
    return IssueLogEntryRead.model_validate(entry)


@issues_router.get("/{issue_id}/logs", response_model=list[IssueLogEntryRead])
async def list_log_entries_endpoint(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[IssueLogEntryRead]:
    try:
        entries = await list_issue_log_entries(db, issue_id)
    except IssueNotFoundError:
        raise HTTPException(status_code=404, detail="Issue not found")
    return [IssueLogEntryRead.model_validate(e) for e in entries]
