"""Claude Code engine adapter: wraps ClaudeCodeProcess + ClaudeCodeParser as an EngineAdapter."""

from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncIterator

from codehive.engine.claude_code import ClaudeCodeProcess
from codehive.engine.claude_code_parser import ClaudeCodeParser
from codehive.execution.diff import DiffService

logger = logging.getLogger(__name__)


class _SessionState:
    """Internal per-session state for a Claude Code engine session."""

    def __init__(self, process: ClaudeCodeProcess) -> None:
        self.process = process
        self.paused: bool = False
        self.pending_actions: dict[str, dict[str, Any]] = {}


class ClaudeCodeEngine:
    """Engine adapter using the Claude Code CLI subprocess.

    Implements the EngineAdapter protocol by delegating to
    :class:`~codehive.engine.claude_code.ClaudeCodeProcess` for subprocess
    management and :class:`~codehive.engine.claude_code_parser.ClaudeCodeParser`
    for parsing stream-json output into codehive events.
    """

    def __init__(
        self,
        diff_service: DiffService,
        *,
        cli_path: str = "claude",
        working_dir: str | None = None,
        extra_flags: list[str] | None = None,
    ) -> None:
        self._diff_service = diff_service
        self._cli_path = cli_path
        self._working_dir = working_dir
        self._extra_flags = extra_flags or []
        self._parser = ClaudeCodeParser()
        self._sessions: dict[uuid.UUID, _SessionState] = {}
        self._task_fetcher: Any = None  # Optional callback for fetching tasks

    # ------------------------------------------------------------------
    # EngineAdapter interface
    # ------------------------------------------------------------------

    async def create_session(self, session_id: uuid.UUID) -> None:
        """Spawn a ClaudeCodeProcess and store it in the internal session map.

        If a session with the same ID already exists, the old process is
        stopped and replaced.
        """
        # Clean up existing session if present
        existing = self._sessions.get(session_id)
        if existing is not None:
            try:
                await existing.process.stop()
            except Exception:
                logger.warning("Failed to stop existing process for session %s", session_id)

        process = ClaudeCodeProcess(
            session_id=session_id,
            cli_path=self._cli_path,
            working_dir=self._working_dir,
            extra_flags=self._extra_flags,
        )
        await process.start()
        self._sessions[session_id] = _SessionState(process=process)

    async def send_message(
        self,
        session_id: uuid.UUID,
        message: str,
        **kwargs: Any,
    ) -> AsyncIterator[dict]:
        """Send a message via the Claude Code CLI process and yield codehive events.

        Reads stdout lines from the process, parses them with ClaudeCodeParser,
        and yields codehive event dicts. If the process crashes mid-stream,
        yields a session.failed event.
        """
        state = self._sessions.get(session_id)
        if state is None:
            raise KeyError(f"Session {session_id} not found. Call create_session first.")

        # Check if paused
        if state.paused:
            yield {"type": "session.paused", "session_id": str(session_id)}
            return

        # Send the message to the process
        await state.process.send(message)

        # Read stdout lines and parse into events
        while True:
            if state.paused:
                yield {"type": "session.paused", "session_id": str(session_id)}
                return

            line = await state.process.read_stdout_line()
            if line is None:
                # EOF -- check if process crashed
                crash_event = await state.process.check_for_crash()
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
            state_new = _SessionState(process=ClaudeCodeProcess(session_id=session_id))
            state_new.paused = True
            self._sessions[session_id] = state_new
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
        """Stop the process and remove session state.

        Called when a session ends or errors out to ensure proper cleanup.
        """
        state = self._sessions.pop(session_id, None)
        if state is not None:
            try:
                await state.process.stop()
            except Exception:
                logger.warning("Failed to stop process for session %s", session_id)
