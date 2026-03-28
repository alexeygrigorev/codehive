"""Issue business logic (DB queries, status transitions, log entries)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from codehive.db.models import Issue, IssueLogEntry, Project
from codehive.db.models import Session as SessionModel


class ProjectNotFoundError(Exception):
    """Raised when a project_id does not exist."""


class IssueNotFoundError(Exception):
    """Raised when an issue is not found by ID."""


class IssueHasLinkedSessionsError(Exception):
    """Raised when an issue cannot be deleted because it has linked sessions."""


class SessionNotFoundError(Exception):
    """Raised when a session is not found by ID."""


class InvalidStatusTransitionError(Exception):
    """Raised when a status transition is not allowed."""


VALID_STATUSES = {"open", "groomed", "in_progress", "done", "closed"}

# Allowed status transitions: from_status -> set of to_statuses
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"groomed", "in_progress", "closed"},
    "groomed": {"in_progress", "closed"},
    "in_progress": {"done", "open", "closed"},
    "done": {"closed", "open"},
    "closed": {"open"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def create_issue(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    title: str,
    description: str | None = None,
    acceptance_criteria: str | None = None,
    assigned_agent: str | None = None,
    priority: int = 0,
) -> Issue:
    """Create a new issue. Raises ProjectNotFoundError if project doesn't exist."""
    project = await db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    now = _now()
    issue = Issue(
        project_id=project_id,
        title=title,
        description=description,
        acceptance_criteria=acceptance_criteria,
        assigned_agent=assigned_agent,
        priority=priority,
        status="open",
        created_at=now,
        updated_at=now,
    )
    db.add(issue)
    await db.commit()
    await db.refresh(issue)
    return issue


async def list_issues(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    status: str | None = None,
    assigned_agent: str | None = None,
) -> list[Issue]:
    """Return all issues for a project, optionally filtered by status and/or assigned_agent.

    Raises ProjectNotFoundError if the project doesn't exist.
    """
    project = await db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    stmt = select(Issue).where(Issue.project_id == project_id)
    if status is not None:
        stmt = stmt.where(Issue.status == status)
    if assigned_agent is not None:
        stmt = stmt.where(Issue.assigned_agent == assigned_agent)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_issue(
    db: AsyncSession,
    issue_id: uuid.UUID,
) -> Issue | None:
    """Return an issue by ID with sessions and logs eagerly loaded, or None if not found."""
    stmt = (
        select(Issue)
        .where(Issue.id == issue_id)
        .options(selectinload(Issue.sessions), selectinload(Issue.logs))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_issue(
    db: AsyncSession,
    issue_id: uuid.UUID,
    **fields: str | int | None,
) -> Issue:
    """Update specific fields on an issue.

    Raises IssueNotFoundError if not found.
    Raises InvalidStatusTransitionError if status transition is not allowed.
    """
    issue = await db.get(Issue, issue_id)
    if issue is None:
        raise IssueNotFoundError(f"Issue {issue_id} not found")

    # Validate status transition if status is being changed
    if "status" in fields and fields["status"] is not None:
        new_status = fields["status"]
        if new_status != issue.status:
            allowed = _ALLOWED_TRANSITIONS.get(issue.status, set())
            if new_status not in allowed:
                raise InvalidStatusTransitionError(
                    f"Cannot transition from '{issue.status}' to '{new_status}'"
                )

    for key, value in fields.items():
        setattr(issue, key, value)

    # Explicitly set updated_at so it works even if onupdate doesn't fire
    issue.updated_at = _now()

    await db.commit()
    await db.refresh(issue)
    return issue


async def delete_issue(
    db: AsyncSession,
    issue_id: uuid.UUID,
) -> None:
    """Delete an issue. Raises IssueNotFoundError if not found.

    Raises IssueHasLinkedSessionsError if sessions are linked.
    """
    issue = await db.get(Issue, issue_id)
    if issue is None:
        raise IssueNotFoundError(f"Issue {issue_id} not found")

    await db.refresh(issue, attribute_names=["sessions"])
    if issue.sessions:
        raise IssueHasLinkedSessionsError(f"Issue {issue_id} has linked sessions")

    await db.delete(issue)
    await db.commit()


async def link_session_to_issue(
    db: AsyncSession,
    issue_id: uuid.UUID,
    session_id: uuid.UUID,
) -> SessionModel:
    """Link a session to an issue by setting session.issue_id.

    Raises IssueNotFoundError if the issue doesn't exist.
    Raises SessionNotFoundError if the session doesn't exist.
    """
    issue = await db.get(Issue, issue_id)
    if issue is None:
        raise IssueNotFoundError(f"Issue {issue_id} not found")

    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    session.issue_id = issue_id
    await db.commit()
    await db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# Issue log entry operations
# ---------------------------------------------------------------------------


async def create_issue_log_entry(
    db: AsyncSession,
    *,
    issue_id: uuid.UUID,
    agent_role: str,
    content: str,
) -> IssueLogEntry:
    """Create a log entry for an issue. Raises IssueNotFoundError if issue doesn't exist."""
    issue = await db.get(Issue, issue_id)
    if issue is None:
        raise IssueNotFoundError(f"Issue {issue_id} not found")

    entry = IssueLogEntry(
        issue_id=issue_id,
        agent_role=agent_role,
        content=content,
        created_at=_now(),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_issue_log_entries(
    db: AsyncSession,
    issue_id: uuid.UUID,
) -> list[IssueLogEntry]:
    """Return all log entries for an issue in chronological order.

    Raises IssueNotFoundError if issue doesn't exist.
    """
    issue = await db.get(Issue, issue_id)
    if issue is None:
        raise IssueNotFoundError(f"Issue {issue_id} not found")

    stmt = (
        select(IssueLogEntry)
        .where(IssueLogEntry.issue_id == issue_id)
        .order_by(IssueLogEntry.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
