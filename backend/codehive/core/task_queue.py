"""Task queue business logic (DB queries, ordering, status transitions, dependency checking)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.db.models import Session as SessionModel
from codehive.db.models import Task


class SessionNotFoundError(Exception):
    """Raised when a session_id does not exist."""


class TaskNotFoundError(Exception):
    """Raised when a task is not found by ID."""


class InvalidStatusTransitionError(Exception):
    """Raised when a status transition is not allowed."""


class InvalidDependencyError(Exception):
    """Raised when depends_on references a task in a different session."""


# Allowed status transitions: from_status -> set of to_statuses
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "blocked", "skipped"},
    "running": {"done", "failed", "blocked"},
    "blocked": {"pending"},
    "failed": {"pending"},
    # Terminal states: done, skipped -> nothing
}


async def _verify_session_exists(db: AsyncSession, session_id: uuid.UUID) -> None:
    """Raise SessionNotFoundError if session does not exist."""
    session = await db.get(SessionModel, session_id)
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")


async def _validate_depends_on(
    db: AsyncSession, depends_on: uuid.UUID, session_id: uuid.UUID
) -> None:
    """Validate that depends_on references an existing task in the same session."""
    dep_task = await db.get(Task, depends_on)
    if dep_task is None:
        raise TaskNotFoundError(f"Dependency task {depends_on} not found")
    if dep_task.session_id != session_id:
        raise InvalidDependencyError(f"Dependency task {depends_on} belongs to a different session")


async def create_task(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    title: str,
    instructions: str | None = None,
    priority: int = 0,
    depends_on: uuid.UUID | None = None,
    mode: str = "auto",
    created_by: str = "user",
) -> Task:
    """Create a new task in a session. Validates session exists and depends_on if provided."""
    await _verify_session_exists(db, session_id)

    if depends_on is not None:
        await _validate_depends_on(db, depends_on, session_id)

    task = Task(
        session_id=session_id,
        title=title,
        instructions=instructions,
        status="pending",
        priority=priority,
        depends_on=depends_on,
        mode=mode,
        created_by=created_by,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def list_tasks(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list[Task]:
    """Return all tasks for a session ordered by priority desc, created_at asc."""
    await _verify_session_exists(db, session_id)

    result = await db.execute(
        select(Task)
        .where(Task.session_id == session_id)
        .order_by(Task.priority.desc(), Task.created_at.asc())
    )
    return list(result.scalars().all())


async def get_task(
    db: AsyncSession,
    task_id: uuid.UUID,
) -> Task | None:
    """Return a task by ID, or None if not found."""
    return await db.get(Task, task_id)


async def update_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    **fields: str | int | uuid.UUID | None,
) -> Task:
    """Update specific fields on a task. Raises TaskNotFoundError if not found."""
    task = await db.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")

    # Validate depends_on if being updated
    if "depends_on" in fields and fields["depends_on"] is not None:
        await _validate_depends_on(db, fields["depends_on"], task.session_id)

    for key, value in fields.items():
        setattr(task, key, value)

    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(
    db: AsyncSession,
    task_id: uuid.UUID,
) -> None:
    """Delete a task. Raises TaskNotFoundError if not found."""
    task = await db.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")

    await db.delete(task)
    await db.commit()


async def transition_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    target_status: str,
) -> Task:
    """Transition a task to a new status. Validates the transition is allowed."""
    task = await db.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found")

    allowed = _ALLOWED_TRANSITIONS.get(task.status, set())
    if target_status not in allowed:
        raise InvalidStatusTransitionError(
            f"Cannot transition from '{task.status}' to '{target_status}'"
        )

    task.status = target_status
    await db.commit()
    await db.refresh(task)
    return task


async def get_next_task(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> Task | None:
    """Return the highest-priority pending task with no unmet dependencies.

    A task is actionable if:
    - status is 'pending'
    - depends_on is null OR the dependency task has status 'done'
    """
    await _verify_session_exists(db, session_id)

    # Get all pending tasks ordered by priority desc, created_at asc
    result = await db.execute(
        select(Task)
        .where(Task.session_id == session_id, Task.status == "pending")
        .order_by(Task.priority.desc(), Task.created_at.asc())
    )
    pending_tasks = result.scalars().all()

    for task in pending_tasks:
        if task.depends_on is None:
            return task
        # Check if dependency is done
        dep = await db.get(Task, task.depends_on)
        # Dangling reference (deleted dependency) treated as no dependency
        if dep is None or dep.status == "done":
            return task

    return None


async def reorder_tasks(
    db: AsyncSession,
    session_id: uuid.UUID,
    items: list[dict[str, uuid.UUID | int]],
) -> list[Task]:
    """Bulk-update priorities for tasks. All task IDs must belong to the given session."""
    await _verify_session_exists(db, session_id)

    for item in items:
        task = await db.get(Task, item["id"])
        if task is None:
            raise InvalidDependencyError(f"Task {item['id']} not found")
        if task.session_id != session_id:
            raise InvalidDependencyError(f"Task {item['id']} belongs to a different session")
        task.priority = item["priority"]

    await db.commit()

    # Return updated task list
    return await list_tasks(db, session_id)
