"""Sub-agent lifecycle: spawn, monitor status, collect structured report."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from codehive.core.events import EventBus
from codehive.core.session import (
    SessionNotFoundError,
    create_session,
    get_session,
)
from codehive.engine.tools.spawn_subagent import VALID_ENGINE_TYPES

logger = logging.getLogger(__name__)


class InvalidEngineError(Exception):
    """Raised when an invalid engine type is specified."""


class InvalidReportError(Exception):
    """Raised when a sub-agent report fails validation."""


_VALID_STATUSES = {"completed", "failed", "blocked"}

# Type alias for engine builder callback
EngineBuilder = Callable[[dict[str, Any], str], Awaitable[Any]]


class SubAgentManager:
    """Manages sub-agent lifecycle: spawning, status queries, and report collection."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        engine_builder: EngineBuilder | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._engine_builder = engine_builder

    async def spawn_subagent(
        self,
        db: AsyncSession,
        *,
        parent_session_id: uuid.UUID,
        mission: str,
        role: str,
        scope: list[str],
        engine: str | None = None,
        initial_message: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Spawn a child session for the given parent.

        Creates a new session via core.session.create_session with
        parent_session_id set.  When *engine* is provided the child
        uses that engine; otherwise it inherits the parent's engine.

        When *initial_message* is provided the child engine is built
        via the ``engine_builder`` callback, a first message is sent,
        and the response text is included in the return dict.

        Returns a dict with the child_session_id and metadata.
        Raises SessionNotFoundError if the parent does not exist.
        Raises InvalidEngineError for unknown engine names.
        """
        parent = await get_session(db, parent_session_id)
        if parent is None:
            raise SessionNotFoundError(f"Session {parent_session_id} not found")

        # Determine child engine
        child_engine = engine if engine is not None else parent.engine

        # Validate engine type
        if child_engine not in VALID_ENGINE_TYPES:
            raise InvalidEngineError(
                f"Unknown engine '{child_engine}'. "
                f"Valid engines: {', '.join(sorted(VALID_ENGINE_TYPES))}"
            )

        child_config: dict[str, Any] = {
            "mission": mission,
            "role": role,
            "scope": scope,
        }
        if config:
            child_config.update(config)

        # Inherit project_root from parent config if available
        parent_config = parent.config or {}
        if "project_root" in parent_config and "project_root" not in child_config:
            child_config["project_root"] = parent_config["project_root"]

        child = await create_session(
            db,
            project_id=parent.project_id,
            name=f"subagent-{role}",
            engine=child_engine,
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
                    "engine": child_engine,
                },
            )

        result: dict[str, Any] = {
            "child_session_id": str(child.id),
            "parent_session_id": str(parent_session_id),
            "mission": mission,
            "role": role,
            "status": child.status,
            "engine": child_engine,
        }

        # Execute initial message if provided
        if initial_message is not None:
            response_text = await self._run_initial_message(
                db,
                child_session_id=child.id,
                child_config=child_config,
                engine_type=child_engine,
                initial_message=initial_message,
            )
            result["response"] = response_text
            result["status"] = "idle"  # After first turn completes

        return result

    async def _run_initial_message(
        self,
        db: AsyncSession,
        *,
        child_session_id: uuid.UUID,
        child_config: dict[str, Any],
        engine_type: str,
        initial_message: str,
    ) -> str:
        """Build the child engine, send the initial message, collect response text."""
        if self._engine_builder is None:
            return "[engine_builder not configured -- child session created but initial message not sent]"

        try:
            child_engine = await self._engine_builder(child_config, engine_type)
        except Exception as exc:
            logger.warning(
                "Failed to build engine '%s' for child %s: %s",
                engine_type,
                child_session_id,
                exc,
            )
            return f"[error building engine: {exc}]"

        try:
            # Create engine session state
            if hasattr(child_engine, "create_session"):
                await child_engine.create_session(child_session_id)

            # Send message and collect text events
            response_parts: list[str] = []
            async for event in child_engine.send_message(child_session_id, initial_message, db=db):
                if event.get("type") == "message.created" and event.get("role") == "assistant":
                    response_parts.append(event.get("content", ""))

            return "".join(response_parts) if response_parts else "[no response]"

        except Exception as exc:
            logger.warning(
                "Initial message failed for child %s: %s",
                child_session_id,
                exc,
            )
            return f"[error executing initial message: {exc}]"

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
