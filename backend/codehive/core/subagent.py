"""Sub-agent lifecycle: spawn, monitor status, collect structured report."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.events import EventBus
from codehive.core.session import (
    SessionNotFoundError,
    create_session,
    get_session,
)


class InvalidReportError(Exception):
    """Raised when a sub-agent report fails validation."""


_VALID_STATUSES = {"completed", "failed", "blocked"}


class SubAgentManager:
    """Manages sub-agent lifecycle: spawning, status queries, and report collection."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    async def spawn_subagent(
        self,
        db: AsyncSession,
        *,
        parent_session_id: uuid.UUID,
        mission: str,
        role: str,
        scope: list[str],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Spawn a child session for the given parent.

        Creates a new session via core.session.create_session with
        parent_session_id set, inheriting project_id and engine from
        the parent session.

        Returns a dict with the child_session_id and metadata.
        Raises SessionNotFoundError if the parent does not exist.
        """
        parent = await get_session(db, parent_session_id)
        if parent is None:
            raise SessionNotFoundError(f"Session {parent_session_id} not found")

        child_config: dict[str, Any] = {
            "mission": mission,
            "role": role,
            "scope": scope,
        }
        if config:
            child_config.update(config)

        child = await create_session(
            db,
            project_id=parent.project_id,
            name=f"subagent-{role}",
            engine=parent.engine,
            mode="execution",
            parent_session_id=parent_session_id,
            config=child_config,
        )

        # Emit subagent.spawned event
        if self._event_bus is not None:
            await self._event_bus.publish(
                db,
                parent_session_id,
                "subagent.spawned",
                {
                    "parent_session_id": str(parent_session_id),
                    "child_session_id": str(child.id),
                    "mission": mission,
                    "role": role,
                },
            )

        return {
            "child_session_id": str(child.id),
            "parent_session_id": str(parent_session_id),
            "mission": mission,
            "role": role,
            "status": child.status,
        }

    async def get_subagent_status(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
    ) -> str:
        """Return the current status of a child session.

        Raises SessionNotFoundError if the session does not exist.
        """
        session = await get_session(db, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} not found")
        return session.status

    async def collect_report(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate and collect a structured report from a sub-agent.

        The report must contain:
        - status: one of "completed", "failed", "blocked"
        - summary: a non-empty string
        - files_changed: a list
        - tests: a dict with integer keys "added" and "passing"
        - warnings: a list

        Returns the validated report dict.
        Raises InvalidReportError on validation failure.
        """
        # Validate status
        status = report.get("status")
        if status not in _VALID_STATUSES:
            raise InvalidReportError(
                f"Invalid status '{status}'. Must be one of: {', '.join(sorted(_VALID_STATUSES))}"
            )

        # Validate summary
        summary = report.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise InvalidReportError("summary must be a non-empty string")

        # Validate files_changed
        files_changed = report.get("files_changed")
        if not isinstance(files_changed, list):
            raise InvalidReportError("files_changed must be a list")

        # Validate tests
        tests = report.get("tests")
        if not isinstance(tests, dict):
            raise InvalidReportError("tests must be a dict with 'added' and 'passing' integer keys")
        if "added" not in tests or "passing" not in tests:
            raise InvalidReportError("tests must have 'added' and 'passing' keys")
        if not isinstance(tests["added"], int) or not isinstance(tests["passing"], int):
            raise InvalidReportError("tests 'added' and 'passing' must be integers")

        # Validate warnings
        warnings = report.get("warnings")
        if not isinstance(warnings, list):
            raise InvalidReportError("warnings must be a list")

        validated = {
            "status": status,
            "summary": summary,
            "files_changed": files_changed,
            "tests": tests,
            "warnings": warnings,
        }

        # Emit subagent.report event
        if self._event_bus is not None:
            await self._event_bus.publish(
                db,
                session_id,
                "subagent.report",
                validated,
            )

        return validated
