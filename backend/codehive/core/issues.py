"""Issue business logic (DB queries)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from codehive.db.models import Issue, Project
from codehive.db.models import Session as SessionModel


class ProjectNotFoundError(Exception):
    """Raised when a project_id does not exist."""


class IssueNotFoundError(Exception):
    """Raised when an issue is not found by ID."""


class IssueHasLinkedSessionsError(Exception):
    """Raised when an issue cannot be deleted because it has linked sessions."""


class SessionNotFoundError(Exception):
    """Raised when a session is not found by ID."""


VALID_STATUSES = {"open", "in_progress", "closed"}


async def create_issue(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    title: str,
    description: str | None = None,
) -> Issue:
    """Create a new issue. Raises ProjectNotFoundError if project doesn't exist."""
    project = await db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    issue = Issue(
        project_id=project_id,
        title=title,
        description=description,
        status="open",
        created_at=datetime.now(timezone.utc),
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
) -> list[Issue]:
    """Return all issues for a project, optionally filtered by status.

    Raises ProjectNotFoundError if the project doesn't exist.
    """
    project = await db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    stmt = select(Issue).where(Issue.project_id == project_id)
    if status is not None:
        stmt = stmt.where(Issue.status == status)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_issue(
    db: AsyncSession,
    issue_id: uuid.UUID,
) -> Issue | None:
    """Return an issue by ID with sessions eagerly loaded, or None if not found."""
    stmt = select(Issue).where(Issue.id == issue_id).options(selectinload(Issue.sessions))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_issue(
    db: AsyncSession,
    issue_id: uuid.UUID,
    **fields: str | None,
) -> Issue:
    """Update specific fields on an issue. Raises IssueNotFoundError if not found."""
    issue = await db.get(Issue, issue_id)
    if issue is None:
        raise IssueNotFoundError(f"Issue {issue_id} not found")

    for key, value in fields.items():
        setattr(issue, key, value)

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
