"""Claude Code engine adapter: fire-and-forget subprocess per message with --resume."""

from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncIterator

from codehive.engine.claude_code import ClaudeCodeProcess, ClaudeProcessError
from codehive.engine.claude_code_parser import ClaudeCodeParser
from codehive.execution.diff import DiffService

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
CONTINUATION_PROMPT = "Continue. You were interrupted."


class _SessionState:
    """Internal per-session state for a Claude Code engine session."""

    def __init__(self) -> None:
        self.claude_session_id: str | None = None
        self.retry_count: int = 0
        self.paused: bool = False
        self.pending_actions: dict[str, dict[str, Any]] = {}


class ClaudeCodeEngine:
    """Engine adapter using fire-and-forget Claude Code CLI subprocesses.

    Each call to :meth:`send_message` spawns a new ``claude -p`` subprocess.
    The first message starts a fresh Claude session; subsequent messages use
    ``--resume {session_id}`` to maintain conversation context.

    Auto-retries on crash (non-zero exit code) up to ``MAX_RETRIES`` times.
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
        self._task_fetcher: Any = None

    # ------------------------------------------------------------------
    # EngineAdapter interface
    # ------------------------------------------------------------------

    async def create_session(self, session_id: uuid.UUID) -> None:
        """Initialise internal state for a new session.

        No subprocess is spawned until :meth:`send_message` is called.
        """
        existing = self._sessions.get(session_id)
        if existing is not None:
            logger.debug("Replacing existing session state for %s", session_id)
        self._sessions[session_id] = _SessionState()

    async def send_message(
        self,
        session_id: uuid.UUID,
        message: str,
        **kwargs: Any,
    ) -> AsyncIterator[dict]:
        """Send a message via a new ``claude -p`` subprocess and yield events.

        Spawns a subprocess per invocation.  On the first message for a session,
        no ``--resume`` flag is used; the ``session_id`` is captured from the
        ``system.init`` event.  Subsequent messages use ``--resume``.

        Auto-retries up to ``MAX_RETRIES`` times on non-zero exit code using
        ``--resume`` with a continuation prompt.
        """
        state = self._sessions.get(session_id)
        if state is None:
            raise KeyError(f"Session {session_id} not found. Call create_session first.")

        if state.paused:
            yield {"type": "session.paused", "session_id": str(session_id)}
            return

        process = ClaudeCodeProcess(
            cli_path=self._cli_path,
            working_dir=self._working_dir,
            extra_flags=self._extra_flags,
        )

        try:
            async for line in process.run(
                message,
                resume_session_id=state.claude_session_id,
            ):
                events = self._parser.parse_line(line, session_id)
                for event in events:
                    # Capture claude_session_id from system.init
                    if event.get("type") == "session.started":
                        claude_sid = event.get("claude_session_id", "")
                        if claude_sid:
                            state.claude_session_id = claude_sid
                    yield event
            # Success -- reset retry count
            state.retry_count = 0
        except ClaudeProcessError as exc:
            logger.warning(
                "Claude process crashed for session %s (exit code %d): %s",
                session_id,
                exc.exit_code,
                exc.stderr[:200],
            )
            # Auto-retry loop
            async for event in self._retry_loop(session_id, state, process):
                yield event

    async def _retry_loop(
        self,
        session_id: uuid.UUID,
        state: _SessionState,
        process: ClaudeCodeProcess,
    ) -> AsyncIterator[dict]:
        """Retry a crashed subprocess up to MAX_RETRIES times using --resume."""
        for attempt in range(1, MAX_RETRIES + 1):
            if not state.claude_session_id:
                yield {
                    "type": "session.failed",
                    "session_id": str(session_id),
                    "error": "Process crashed and no claude session ID available for resume",
                }
                return

            logger.info(
                "Auto-retry %d/%d for session %s with --resume %s",
                attempt,
                MAX_RETRIES,
                session_id,
                state.claude_session_id[:8],
            )

            retry_process = ClaudeCodeProcess(
                cli_path=self._cli_path,
                working_dir=self._working_dir,
                extra_flags=self._extra_flags,
            )

            try:
                async for line in retry_process.run(
                    CONTINUATION_PROMPT,
                    resume_session_id=state.claude_session_id,
                ):
                    events = self._parser.parse_line(line, session_id)
                    for event in events:
                        if event.get("type") == "session.started":
                            claude_sid = event.get("claude_session_id", "")
                            if claude_sid:
                                state.claude_session_id = claude_sid
                        yield event
                # Retry succeeded
                state.retry_count = 0
                return
            except ClaudeProcessError as exc:
                logger.warning(
                    "Retry %d/%d also crashed (exit code %d)",
                    attempt,
                    MAX_RETRIES,
                    exc.exit_code,
                )
                state.retry_count = attempt

        # All retries exhausted
        yield {
            "type": "session.failed",
            "session_id": str(session_id),
            "error": f"Process crashed {MAX_RETRIES + 1} times, all retries exhausted",
        }

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
        """Set the pause flag so send_message yields session.paused immediately."""
        state = self._sessions.get(session_id)
        if state is None:
            state = _SessionState()
            state.paused = True
            self._sessions[session_id] = state
            return
        state.paused = True

    async def resume(self, session_id: uuid.UUID) -> None:
        """Clear the pause flag."""
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
        """Remove session state.

        In the fire-and-forget model there is no long-running process to
        stop -- we simply discard the stored state.
        """
        self._sessions.pop(session_id, None)
