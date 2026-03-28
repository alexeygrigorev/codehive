"""Shared service for creating backlog tasks (Issue + Task).

Used by both the ``POST /api/orchestrator/add-task`` endpoint and the
``create_task`` engine tool so that the logic is not duplicated.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.events import EventBus, LocalEventBus
from codehive.core.issues import ProjectNotFoundError, create_issue
from codehive.core.task_queue import create_task
from codehive.db.models import Project
from codehive.db.models import Session as SessionModel


class ProjectNotFoundForBacklogError(Exception):
    """Raised when the project does not exist."""


@dataclass
class BacklogResult:
    """Result of creating an issue + backlog task."""

    issue_id: uuid.UUID
    task_id: uuid.UUID
    pipeline_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": str(self.issue_id),
            "task_id": str(self.task_id),
            "pipeline_status": self.pipeline_status,
        }


async def create_backlog_task(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    title: str,
    description: str | None = None,
    acceptance_criteria: str | None = None,
    event_bus: EventBus | LocalEventBus | None = None,
) -> BacklogResult:
    """Create an Issue (status 'open') and a Task (pipeline_status 'backlog').

    Finds or creates an orchestrator session for the project and attaches the
    task to it.

    Raises ``ProjectNotFoundForBacklogError`` if the project does not exist.
    """
    # Verify project exists
    project = await db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundForBacklogError(f"Project {project_id} not found")

    # Create the issue
    try:
        issue = await create_issue(
            db,
            project_id=project_id,
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria,
        )
    except ProjectNotFoundError:
        raise ProjectNotFoundForBacklogError(f"Project {project_id} not found")

    # Find or create an orchestrator session for the project
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.project_id == project_id,
            SessionModel.name == f"orchestrator-{project_id}",
        )
    )
    orch_session = result.scalar_one_or_none()
    if orch_session is None:
        from codehive.core.session import create_session as create_db_session

        orch_session = await create_db_session(
            db,
            project_id=project_id,
            name=f"orchestrator-{project_id}",
            engine="claude_code",
            mode="orchestrator",
            issue_id=issue.id,
        )

    # Create the task in backlog
    task = await create_task(
        db,
        session_id=orch_session.id,
        title=title,
        instructions=description,
        pipeline_status="backlog",
    )

    # Emit task.created event
    if event_bus is not None:
        await event_bus.publish(
            db,
            orch_session.id,
            "task.created",
            {
                "issue_id": str(issue.id),
                "task_id": str(task.id),
                "title": title,
                "pipeline_status": "backlog",
            },
        )

    return BacklogResult(
        issue_id=issue.id,
        task_id=task.id,
        pipeline_status="backlog",
    )
