"""Claude Code CLI process manager: spawn, communicate, terminate."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from codehive.engine.claude_code_parser import ClaudeCodeParser

logger = logging.getLogger(__name__)


class ClaudeCodeProcess:
    """Manages a single Claude Code CLI subprocess for one session.

    Spawns ``claude --print --output-format stream-json --input-format stream-json``
    as an async subprocess, sends user messages via stdin as newline-delimited
    JSON, and reads stdout line-by-line for parsing.

    Args:
        session_id: Unique identifier for the session this process serves.
        cli_path: Path to the ``claude`` CLI binary.  Defaults to ``"claude"``.
        working_dir: Working directory for the subprocess (project root).
        extra_flags: Additional CLI flags to pass (e.g. ``["--model", "opus"]``).
    """

    def __init__(
        self,
        session_id: uuid.UUID,
        *,
        cli_path: str = "claude",
        working_dir: str | None = None,
        extra_flags: list[str] | None = None,
    ) -> None:
        self.session_id = session_id
        self.cli_path = cli_path
        self.working_dir = working_dir
        self.extra_flags = extra_flags or []
        self.parser = ClaudeCodeParser()

        self._process: asyncio.subprocess.Process | None = None
        self._stderr_output: str = ""

    def _build_command(self) -> list[str]:
        """Build the CLI command list."""
        cmd = [
            self.cli_path,
            "--print",
            "--output-format",
            "stream-json",
            "--input-format",
            "stream-json",
        ]
        cmd.extend(self.extra_flags)
        return cmd

    async def start(self) -> None:
        """Spawn the Claude Code CLI subprocess.

        Raises:
            RuntimeError: If the process is already running.
        """
        if self._process is not None and self._process.returncode is None:
            raise RuntimeError("Process is already running")

        cmd = self._build_command()

        kwargs: dict[str, Any] = {
            "stdin": asyncio.subprocess.PIPE,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        if self.working_dir is not None:
            kwargs["cwd"] = self.working_dir

        self._process = await asyncio.create_subprocess_exec(*cmd, **kwargs)
        self._stderr_output = ""

    async def send(self, message: str) -> None:
        """Send a user message to the process via stdin as newline-delimited JSON.

        Args:
            message: The user's text message.

        Raises:
            RuntimeError: If the process is not running or stdin is unavailable.
        """
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Process is not running or stdin is unavailable")

        payload = json.dumps({"type": "user", "content": message})
        self._process.stdin.write((payload + "\n").encode())
        await self._process.stdin.drain()

    async def stop(self) -> None:
        """Terminate the subprocess gracefully.

        Sends SIGTERM and waits for the process to exit.  If the process
        does not exit within 5 seconds, it is killed.
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
