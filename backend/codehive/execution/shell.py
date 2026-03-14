"""Async subprocess execution with streaming, timeout, and working directory support."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator


@dataclass
class ShellResult:
    """Result of a shell command execution."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class ShellRunner:
    """Async shell command runner with streaming and timeout support."""

    async def run(
        self,
        command: str | list[str],
        working_dir: Path,
        timeout_seconds: float = 30.0,
        env: dict[str, str] | None = None,
    ) -> ShellResult:
        """Run a command and return the collected result.

        Args:
            command: Shell command string or argument list.
            working_dir: Directory to run the command in. Must exist.
            timeout_seconds: Maximum seconds before the process is killed.
            env: Optional environment variables (merged with system env if provided).

        Returns:
            ShellResult with exit_code, stdout, stderr, and timed_out flag.

        Raises:
            FileNotFoundError: If working_dir does not exist.
        """
        working_dir = Path(working_dir)
        if not working_dir.exists():
            raise FileNotFoundError(f"Working directory does not exist: {working_dir}")

        if isinstance(command, list):
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env,
            )
        else:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env,
            )

        timed_out = False
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            timed_out = True
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            stdout_bytes = b""
            stderr_bytes = b""

        return ShellResult(
            exit_code=process.returncode if process.returncode is not None else -1,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            timed_out=timed_out,
        )

    async def run_streaming(
        self,
        command: str | list[str],
        working_dir: Path,
        timeout_seconds: float = 30.0,
        env: dict[str, str] | None = None,
    ) -> AsyncIterator[str]:
        """Run a command and yield stdout lines as they are produced.

        Args:
            command: Shell command string or argument list.
            working_dir: Directory to run the command in. Must exist.
            timeout_seconds: Maximum seconds before the process is killed.
            env: Optional environment variables.

        Yields:
            Lines from stdout as they become available.

        Raises:
            FileNotFoundError: If working_dir does not exist.
        """
        working_dir = Path(working_dir)
        if not working_dir.exists():
            raise FileNotFoundError(f"Working directory does not exist: {working_dir}")

        if isinstance(command, list):
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env,
            )
        else:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env,
            )

        assert process.stdout is not None

        async def _read_lines() -> AsyncIterator[str]:
            async for line_bytes in process.stdout:  # type: ignore[union-attr]
                yield line_bytes.decode("utf-8", errors="replace").rstrip("\n")

        try:
            async with asyncio.timeout(timeout_seconds):
                async for line in _read_lines():
                    yield line
        except TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass

        await process.wait()
