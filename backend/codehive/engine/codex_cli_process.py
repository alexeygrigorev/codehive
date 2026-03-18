"""Codex CLI process manager: spawn, communicate, terminate."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class CodexCLIProcess:
    """Manages a single ``codex exec`` CLI subprocess for one session.

    Unlike :class:`~codehive.engine.claude_code.ClaudeCodeProcess` which
    maintains a long-running process with stdin streaming, ``codex exec`` is
    non-interactive: it takes a prompt as a positional argument, runs to
    completion, then exits.  Each :meth:`send` call therefore spawns a fresh
    subprocess.

    Args:
        session_id: Unique identifier for the session this process serves.
        cli_path: Path to the ``codex`` CLI binary.  Defaults to ``"codex"``.
        working_dir: Working directory for the subprocess (project root).
        model: Model name to pass via ``--model``.  Defaults to ``"codex-mini-latest"``.
        extra_flags: Additional CLI flags (e.g. ``["--sandbox"]``).
    """

    def __init__(
        self,
        session_id: uuid.UUID,
        *,
        cli_path: str = "codex",
        working_dir: str | None = None,
        model: str = "codex-mini-latest",
        extra_flags: list[str] | None = None,
    ) -> None:
        self.session_id = session_id
        self.cli_path = cli_path
        self.working_dir = working_dir
        self.model = model
        self.extra_flags = extra_flags or []

        self._process: asyncio.subprocess.Process | None = None
        self._stderr_output: str = ""

    def _build_command(self, prompt: str) -> list[str]:
        """Build the CLI command list for a given prompt."""
        cmd = [
            self.cli_path,
            "exec",
            "--json",
            "--full-auto",
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        if self.working_dir:
            cmd.extend(["-C", self.working_dir])
        cmd.extend(self.extra_flags)
        cmd.append(prompt)
        return cmd

    async def send(self, prompt: str) -> None:
        """Spawn a new ``codex exec`` subprocess with the given prompt.

        Each call starts a fresh process since ``codex exec`` is
        non-interactive.  Any previously running process is stopped first.

        Args:
            prompt: The user's text message / prompt.
        """
        # Stop any existing process
        if self._process is not None and self._process.returncode is None:
            await self.stop()

        cmd = self._build_command(prompt)

        kwargs: dict[str, Any] = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }

        self._process = await asyncio.create_subprocess_exec(*cmd, **kwargs)
        self._stderr_output = ""

    def is_alive(self) -> bool:
        """Return True if the subprocess is currently running."""
        if self._process is None:
            return False
        return self._process.returncode is None

    async def read_stdout_line(self) -> str | None:
        """Read a single line from the process stdout.

        Returns:
            The line as a string (without trailing newline), or None if
            stdout is closed / EOF.
        """
        if self._process is None or self._process.stdout is None:
            return None

        line = await self._process.stdout.readline()
        if not line:
            return None
        return line.decode().rstrip("\n")

    async def read_stderr(self) -> str:
        """Read all available stderr output.

        Returns:
            The accumulated stderr content as a string.
        """
        if self._process is None or self._process.stderr is None:
            return self._stderr_output

        try:
            data = await asyncio.wait_for(self._process.stderr.read(), timeout=0.1)
            self._stderr_output += data.decode()
        except asyncio.TimeoutError:
            pass

        return self._stderr_output

    async def check_for_crash(self) -> dict | None:
        """Check if the process exited unexpectedly and return a failure event.

        Returns:
            A ``session.failed`` event dict if the process crashed (non-zero
            exit code), or None if the process is still running or exited
            cleanly.
        """
        if self._process is None:
            return None

        if self._process.returncode is None:
            return None

        if self._process.returncode == 0:
            return None

        # Process crashed -- gather stderr
        stderr = await self.read_stderr()
        return {
            "type": "session.failed",
            "session_id": str(self.session_id),
            "exit_code": self._process.returncode,
            "error": stderr or f"Process exited with code {self._process.returncode}",
        }

    async def stop(self) -> None:
        """Terminate the subprocess gracefully.

        Sends SIGTERM and waits up to 5 seconds.  If the process does not
        exit in time, it is killed.
        """
        if self._process is None:
            return

        if self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
