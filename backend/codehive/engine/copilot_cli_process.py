"""GitHub Copilot CLI process manager: fire-and-forget subprocess per message."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)


class CopilotCLIProcess:
    """Runs a single ``copilot -p`` invocation and streams stdout lines.

    Each call to :meth:`run` spawns a new subprocess that exits when the
    turn is complete.  Like :class:`~codehive.engine.claude_code.ClaudeCodeProcess`,
    this is a fire-and-forget model -- no long-running process.

    Args:
        cli_path: Path to the ``copilot`` CLI binary.  Defaults to ``"copilot"``.
        working_dir: Working directory for the subprocess (project root).
        extra_flags: Additional CLI flags to pass.
    """

    def __init__(
        self,
        *,
        cli_path: str = "copilot",
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
            "json",
            "--allow-all-tools",
            "--autopilot",
            "--no-auto-update",
        ]
        if resume_session_id:
            cmd.append(f"--resume={resume_session_id}")
        if self.working_dir:
            cmd.extend(["--add-dir", self.working_dir])
        cmd.extend(self.extra_flags)
        return cmd

    async def run(
        self,
        message: str,
        *,
        resume_session_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Spawn ``copilot -p``, yield stdout lines, return when process exits.

        Args:
            message: The prompt text to send.
            resume_session_id: If provided, adds ``--resume=<id>`` to continue
                a previous Copilot session.

        Yields:
            Each non-empty stdout line as a string.

        Raises:
            CopilotProcessError: When the process exits with a non-zero code.
        """
        cmd = self._build_command(message, resume_session_id=resume_session_id)

        kwargs: dict[str, Any] = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }

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
            raise CopilotProcessError(
                exit_code=process.returncode or 1,
                stderr=stderr_data.decode(),
            )


class CopilotProcessError(Exception):
    """Raised when a ``copilot -p`` invocation exits with a non-zero code."""

    def __init__(self, exit_code: int, stderr: str) -> None:
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"copilot exited with code {exit_code}: {stderr[:200]}")
