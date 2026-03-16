"""Auto-session trigger logic: decide whether to create a session for a webhook event."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.session import create_session
from codehive.db.models import Issue
from codehive.integrations.github.mapper import map_github_issue
from codehive.integrations.github.solver import solve_issue
from codehive.integrations.github.webhook import WebhookEvent

# Actions that should trigger session creation in auto mode
_SESSION_CREATING_ACTIONS = {"opened", "reopened"}

MAX_SESSION_NAME_LENGTH = 255


@dataclass
class TriggerResult:
    """Result of processing a webhook event."""

    issue_id: uuid.UUID | None
    session_id: uuid.UUID | None
    action_taken: str  # "imported", "suggested", "session_created", "ignored"


async def _upsert_issue(
    db: AsyncSession,
    project_id: uuid.UUID,
    gh_issue: dict,
) -> Issue:
    """Import or update a single issue from a GitHub issue payload."""
    mapped = map_github_issue(gh_issue)

    stmt = select(Issue).where(
        Issue.project_id == project_id,
        Issue.github_issue_id == mapped["github_issue_id"],
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        existing.title = mapped["title"]
        existing.description = mapped["description"]
        existing.status = mapped["status"]
        await db.commit()
        await db.refresh(existing)
        return existing

    issue = Issue(
        project_id=project_id,
        title=mapped["title"],
        description=mapped["description"],
        status=mapped["status"],
        github_issue_id=mapped["github_issue_id"],
        created_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    await db.commit()
    await db.refresh(issue)
    return issue


def _session_name_from_issue(gh_issue: dict) -> str:
    """Derive a session name from a GitHub issue, e.g. 'GH#42: Fix login bug'."""
    number = gh_issue.get("number", 0)
    title = gh_issue.get("title", "Untitled")
    name = f"GH#{number}: {title}"
    if len(name) > MAX_SESSION_NAME_LENGTH:
        name = name[:MAX_SESSION_NAME_LENGTH]
    return name


async def handle_issue_event(
    db: AsyncSession,
    project_id: uuid.UUID,
    event: WebhookEvent,
    trigger_mode: str = "manual",
    *,
    solver_deps: dict[str, Any] | None = None,
) -> TriggerResult:
    """Handle an issue webhook event.

    1. Import/upsert the issue from the event payload.
    2. Based on trigger_mode, optionally create a session.

    Returns a TriggerResult indicating what was done.
    """
    gh_issue = event.payload.get("issue", {})

    # Upsert the issue
    issue = await _upsert_issue(db, project_id, gh_issue)

    if trigger_mode == "manual":
        return TriggerResult(
            issue_id=issue.id,
            session_id=None,
            action_taken="imported",
        )

    if trigger_mode == "suggest":
        return TriggerResult(
            issue_id=issue.id,
            session_id=None,
            action_taken="suggested",
        )

    if trigger_mode == "auto":
        # Only create sessions for opened/reopened, not closed/edited
        if event.action in _SESSION_CREATING_ACTIONS:
            session_name = _session_name_from_issue(gh_issue)
            session = await create_session(
                db,
                project_id=project_id,
                name=session_name,
                engine="native",
                mode="execution",
                issue_id=issue.id,
            )

            # Launch solver as a background task (fire-and-forget)
            if solver_deps is not None:
                asyncio.create_task(
                    solve_issue(
                        db=solver_deps["db"],
                        project_id=project_id,
                        issue_id=issue.id,
                        session_id=session.id,
                        engine=solver_deps["engine"],
                        git_ops=solver_deps["git_ops"],
                        shell_runner=solver_deps["shell_runner"],
                        test_command=solver_deps.get("test_command"),
                    )
                )

            return TriggerResult(
                issue_id=issue.id,
                session_id=session.id,
                action_taken="session_created",
            )
        else:
            # closed, edited, etc. -- just import
            return TriggerResult(
                issue_id=issue.id,
                session_id=None,
                action_taken="imported",
            )

    # Unknown trigger mode -- treat as manual
    return TriggerResult(
        issue_id=issue.id,
        session_id=None,
        action_taken="imported",
    )
