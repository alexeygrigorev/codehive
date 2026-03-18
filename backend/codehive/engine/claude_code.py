"""Claude Code CLI process manager: fire-and-forget subprocess per message."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)


class ClaudeCodeProcess:
    """Runs a single ``claude -p`` invocation and streams stdout lines.

    Each call to :meth:`run` spawns a new subprocess that exits when the
    turn is complete.  This replaces the old long-running interactive process
    model that used ``--input-format stream-json`` with stdin pipes.

    Args:
        cli_path: Path to the ``claude`` CLI binary.  Defaults to ``"claude"``.
        working_dir: Working directory for the subprocess (project root).
        extra_flags: Additional CLI flags to pass (e.g. ``["--model", "opus"]``).
    """

    def __init__(
        self,
        *,
        cli_path: str = "claude",
        working_dir: str | None = None,
        extra_flags: list[str] | None = None,
    ) -> None:
        self.cli_path = cli_path
        self.working_dir = working_dir
        self.extra_flags = extra_flags or []

    def _build_command(
        self,
        message: str,
        *,
        resume_session_id: str | None = None,
    ) -> list[str]:
        """Build the CLI command list for a single invocation."""
        cmd = [
            self.cli_path,
            "-p",
            message,
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if resume_session_id:
            cmd.extend(["--resume", resume_session_id])
        cmd.extend(self.extra_flags)
        return cmd

    async def run(
        self,
        message: str,
        *,
        resume_session_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Spawn ``claude -p``, yield stdout lines, return when process exits.

        Args:
            message: The prompt text to send.
            resume_session_id: If provided, adds ``--resume {id}`` to continue
                a previous Claude session.

        Yields:
            Each non-empty stdout line as a string.

        Returns:
            When the process exits with code 0.

        Raises:
            ClaudeProcessError: When the process exits with a non-zero code.
        """
        cmd = self._build_command(message, resume_session_id=resume_session_id)

        kwargs: dict[str, Any] = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        if self.working_dir is not None:
            kwargs["cwd"] = self.working_dir

        process = await asyncio.create_subprocess_exec(*cmd, **kwargs)

        assert process.stdout is not None
        assert process.stderr is not None

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded = line.decode().rstrip("\n")
            if decoded:
                yield decoded

        await process.wait()

        if process.returncode != 0:
            stderr_data = await process.stderr.read()
            raise ClaudeProcessError(
                exit_code=process.returncode or 1,
                stderr=stderr_data.decode(),
            )


class ClaudeProcessError(Exception):
    """Raised when a ``claude -p`` invocation exits with a non-zero code."""

    def __init__(self, exit_code: int, stderr: str) -> None:
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"claude exited with code {exit_code}: {stderr[:200]}")
