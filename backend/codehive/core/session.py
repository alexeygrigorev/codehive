"""Session business logic (DB queries, state machine)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.schemas.session import QueueEmptyAction
from codehive.db.models import Issue, Project
from codehive.db.models import Session as SessionModel


class ProjectNotFoundError(Exception):
    """Raised when a project_id does not exist."""


class IssueNotFoundError(Exception):
    """Raised when an issue_id does not exist."""


class SessionNotFoundError(Exception):
    """Raised when a session is not found by ID."""


class SessionHasDependentsError(Exception):
    """Raised when a session cannot be deleted because it has child sessions."""


class InvalidStatusTransitionError(Exception):
    """Raised when a status transition is not allowed."""


def _validate_queue_empty_action(config: dict | None) -> None:
    """Raise ValueError if config contains an invalid queue_empty_action."""
    if config is None:
        return
    action = config.get("queue_empty_action")
    if action is not None and action not in QueueEmptyAction.values():
        raise ValueError(
            f"Invalid queue_empty_action '{action}'. "
            f"Must be one of: {', '.join(sorted(QueueEmptyAction.values()))}"
        )


# Statuses from which pause is allowed
_PAUSABLE_STATUSES = {"idle", "planning", "executing"}


async def create_session(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    name: str,
    engine: str,
    mode: str,
    issue_id: uuid.UUID | None = None,
    parent_session_id: uuid.UUID | None = None,
    config: dict | None = None,
) -> SessionModel:
    """Create a new session. Validates project, issue, and parent session exist."""
    _validate_queue_empty_action(config)

    project = await db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    if issue_id is not None:
        issue = await db.get(Issue, issue_id)
        if issue is None:
            raise IssueNotFoundError(f"Issue {issue_id} not found")

    if parent_session_id is not None:
        parent = await db.get(SessionModel, parent_session_id)
        if parent is None:
            raise SessionNotFoundError(f"Session {parent_session_id} not found")

    session = SessionModel(
        project_id=project_id,
        name=name,
        engine=engine,
        mode=mode,
        status="idle",
        issue_id=issue_id,
        parent_session_id=parent_session_id,
        config=config if config is not None else {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> list[SessionModel]:
    """Return all sessions for a given project. Raises ProjectNotFoundError if project doesn't exist."""
    project = await db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {project_id} not found")

    result = await db.execute(select(SessionModel).where(SessionModel.project_id == project_id))
    return list(result.scalars().all())


async def get_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> SessionModel | None:
    """Return a session by ID, or None if not found."""
    return await db.get(SessionModel, session_id)


async def update_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    **fields: str | dict | None,
) -> SessionModel:
    """Update specific fields on a session. Raises SessionNotFoundError if not found."""
    if "config" in fields:
        _validate_queue_empty_action(fields["config"])

    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    for key, value in fields.items():
        setattr(session, key, value)

    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> None:
    """Delete a session. Raises SessionNotFoundError if not found.

    Raises SessionHasDependentsError if the session has child sessions.
    """
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    await db.refresh(session, attribute_names=["child_sessions"])
    if session.child_sessions:
        raise SessionHasDependentsError(f"Session {session_id} has child sessions")

    await db.delete(session)
    await db.commit()


async def list_child_sessions(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list[SessionModel]:
    """Return all sessions where parent_session_id == session_id.

    Raises SessionNotFoundError if the parent session does not exist.
    """
    parent = await db.get(SessionModel, session_id)
    if parent is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    result = await db.execute(
        select(SessionModel).where(SessionModel.parent_session_id == session_id)
    )
    return list(result.scalars().all())


async def get_session_tree(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> dict:
    """Return the session plus all its direct children (one level deep).

    Returns a dict with 'session' and 'children' keys.
    Raises SessionNotFoundError if the session does not exist.
    """
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    children = await list_child_sessions(db, session_id)
    return {"session": session, "children": children}


async def pause_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> SessionModel:
    """Pause a session (set status to 'blocked').

    Allowed from: idle, planning, executing.
    Raises InvalidStatusTransitionError otherwise.
    """
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    if session.status not in _PAUSABLE_STATUSES:
        raise InvalidStatusTransitionError(
            f"Cannot pause session in '{session.status}' status. "
            f"Pause is only allowed from: {', '.join(sorted(_PAUSABLE_STATUSES))}"
        )

    session.status = "blocked"
    await db.commit()
    await db.refresh(session)
    return session


async def resume_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> SessionModel:
    """Resume a session (set status to 'idle').

    Allowed only from: blocked.
    Raises InvalidStatusTransitionError otherwise.
    """
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    if session.status != "blocked":
        raise InvalidStatusTransitionError(
            f"Cannot resume session in '{session.status}' status. "
            f"Resume is only allowed from: blocked"
        )

    session.status = "idle"
    await db.commit()
    await db.refresh(session)
    return session
