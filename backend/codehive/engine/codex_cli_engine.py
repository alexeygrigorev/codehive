"""Codex CLI engine adapter: wraps CodexCLIProcess + CodexCLIParser as an EngineAdapter."""

from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncIterator

from codehive.engine.codex_cli_parser import CodexCLIParser
from codehive.engine.codex_cli_process import CodexCLIProcess
from codehive.execution.diff import DiffService

logger = logging.getLogger(__name__)


class _SessionState:
    """Internal per-session state for a Codex CLI engine session."""

    def __init__(self) -> None:
        self.process: CodexCLIProcess | None = None
        self.paused: bool = False
        self.pending_actions: dict[str, dict[str, Any]] = {}


class CodexCLIEngine:
    """Engine adapter using the Codex CLI subprocess.

    Implements the EngineAdapter protocol by delegating to
    :class:`~codehive.engine.codex_cli_process.CodexCLIProcess` for subprocess
    management and :class:`~codehive.engine.codex_cli_parser.CodexCLIParser`
    for parsing JSONL output into codehive events.

    Unlike :class:`~codehive.engine.claude_code_engine.ClaudeCodeEngine` which
    maintains a long-running process, each :meth:`send_message` call spawns a
    fresh ``codex exec`` subprocess since the CLI is non-interactive.
    """

    def __init__(
        self,
        diff_service: DiffService,
        *,
        cli_path: str = "codex",
        working_dir: str | None = None,
        model: str = "codex-mini-latest",
        extra_flags: list[str] | None = None,
    ) -> None:
        self._diff_service = diff_service
        self._cli_path = cli_path
        self._working_dir = working_dir
        self._model = model
        self._extra_flags = extra_flags or []
        self._parser = CodexCLIParser()
        self._sessions: dict[uuid.UUID, _SessionState] = {}
        self._task_fetcher: Any = None  # Optional callback for fetching tasks

    # ------------------------------------------------------------------
    # EngineAdapter interface
    # ------------------------------------------------------------------

    async def create_session(self, session_id: uuid.UUID) -> None:
        """Initialize internal session state.

        No subprocess is spawned here since ``codex exec`` is per-invocation.
        If a session with the same ID already exists, its running process (if
        any) is stopped and the state is replaced.
        """
        existing = self._sessions.get(session_id)
        if existing is not None and existing.process is not None:
            try:
                await existing.process.stop()
            except Exception:
                logger.warning("Failed to stop existing process for session %s", session_id)

        self._sessions[session_id] = _SessionState()

    async def send_message(
        self,
        session_id: uuid.UUID,
        message: str,
        **kwargs: Any,
    ) -> AsyncIterator[dict]:
        """Spawn a ``codex exec`` subprocess and yield codehive events.

        Each call creates a fresh subprocess with the message as the prompt,
        reads JSONL stdout line by line, parses via CodexCLIParser, and yields
        codehive event dicts.  If the process crashes, yields a
        ``session.failed`` event.
        """
        state = self._sessions.get(session_id)
        if state is None:
            raise KeyError(f"Session {session_id} not found. Call create_session first.")

        # Check if paused
        if state.paused:
            yield {"type": "session.paused", "session_id": str(session_id)}
            return

        # Create a fresh process for this invocation
        process = CodexCLIProcess(
            session_id=session_id,
            cli_path=self._cli_path,
            working_dir=self._working_dir,
            model=self._model,
            extra_flags=self._extra_flags,
        )
        state.process = process

        # Spawn the subprocess with the message as prompt
        await process.send(message)

        # Read stdout lines and parse into events
        while True:
            if state.paused:
                yield {"type": "session.paused", "session_id": str(session_id)}
                return

            line = await process.read_stdout_line()
            if line is None:
                # EOF -- check if process crashed
                crash_event = await process.check_for_crash()
                if crash_event is not None:
                    yield crash_event
                return

            events = self._parser.parse_line(line, session_id)
            for event in events:
                yield event

    async def start_task(
        self,
        session_id: uuid.UUID,
        task_id: uuid.UUID,
        *,
        task_instructions: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict]:
        """Fetch task instructions and delegate to send_message."""
        if task_instructions is None and self._task_fetcher is not None:
            task_data = await self._task_fetcher(task_id)
            task_instructions = task_data.get("instructions", "")
        elif task_instructions is None:
            task_instructions = f"Execute task {task_id}"

        async for event in self.send_message(session_id, task_instructions):
            yield event

    async def pause(self, session_id: uuid.UUID) -> None:
        """Set the pause flag so the stdout reading loop stops at the next opportunity."""
        state = self._sessions.get(session_id)
        if state is None:
            state = _SessionState()
            state.paused = True
            self._sessions[session_id] = state
            return
        state.paused = True

    async def resume(self, session_id: uuid.UUID) -> None:
        """Clear the pause flag, allowing the stdout reading loop to continue."""
        state = self._sessions.get(session_id)
        if state is not None:
            state.paused = False

    async def approve_action(self, session_id: uuid.UUID, action_id: str) -> None:
        """Approve a pending action."""
        state = self._sessions.get(session_id)
        if state is not None and action_id in state.pending_actions:
            state.pending_actions[action_id]["approved"] = True

    async def reject_action(self, session_id: uuid.UUID, action_id: str) -> None:
        """Reject a pending action."""
        state = self._sessions.get(session_id)
        if state is not None and action_id in state.pending_actions:
            state.pending_actions[action_id]["rejected"] = True

    async def get_diff(self, session_id: uuid.UUID) -> dict[str, str]:
        """Return the accumulated diff for the session via DiffService."""
        return self._diff_service.get_session_changes(str(session_id))

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    async def cleanup_session(self, session_id: uuid.UUID) -> None:
        """Stop any running process and remove session state.

        Called when a session ends or errors out to ensure proper cleanup.
        """
        state = self._sessions.pop(session_id, None)
        if state is not None and state.process is not None:
            try:
                await state.process.stop()
            except Exception:
                logger.warning("Failed to stop process for session %s", session_id)
