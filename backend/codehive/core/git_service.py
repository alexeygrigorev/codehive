"""Git operations service for automated commits after PM acceptance.

All subprocess calls are wrapped in asyncio.to_thread to avoid blocking
the event loop.  Follows the subprocess pattern from backup.py.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codehive.db.models import Project, Task

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Raised when a git operation fails."""

    def __init__(self, message: str, exit_code: int = 1, stderr: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess[bytes]:
    """Run a git command synchronously (called via asyncio.to_thread)."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=False,
    )


class GitService:
    """Static methods for git operations on project directories."""

    @staticmethod
    async def repo_status(path: str) -> dict:
        """Return current branch, dirty file count, and last commit SHA.

        Raises GitError if the path is not a valid git repository.
        """
        # Check if it's a git repo
        result = await asyncio.to_thread(_run_git, ["rev-parse", "--is-inside-work-tree"], path)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise GitError(
                f"Not a git repository: {path}",
                exit_code=result.returncode,
                stderr=stderr,
            )

        # Get current branch
        result = await asyncio.to_thread(_run_git, ["rev-parse", "--abbrev-ref", "HEAD"], path)
        branch = result.stdout.decode("utf-8", errors="replace").strip()

        # Get dirty file count
        result = await asyncio.to_thread(_run_git, ["status", "--porcelain"], path)
        dirty_lines = [
            line
            for line in result.stdout.decode("utf-8", errors="replace").splitlines()
            if line.strip()
        ]
        dirty_count = len(dirty_lines)

        # Get last commit SHA
        result = await asyncio.to_thread(_run_git, ["rev-parse", "HEAD"], path)
        if result.returncode != 0:
            sha = ""
        else:
            sha = result.stdout.decode("utf-8", errors="replace").strip()

        return {
            "branch": branch,
            "dirty_count": dirty_count,
            "last_sha": sha,
        }

    @staticmethod
    async def stage_all(path: str) -> None:
        """Run ``git add -A`` in the given directory."""
        result = await asyncio.to_thread(_run_git, ["add", "-A"], path)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise GitError(
                f"git add -A failed: {stderr}",
                exit_code=result.returncode,
                stderr=stderr,
            )

    @staticmethod
    async def commit(path: str, message: str) -> str:
        """Run ``git commit -m <message>`` and return the commit SHA.

        Raises GitError if there is nothing to commit or the commit fails.
        """
        result = await asyncio.to_thread(_run_git, ["commit", "-m", message], path)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            msg = stderr or stdout
            raise GitError(
                f"git commit failed: {msg}",
                exit_code=result.returncode,
                stderr=stderr,
            )

        # Extract the SHA from the commit output
        sha_result = await asyncio.to_thread(_run_git, ["rev-parse", "HEAD"], path)
        sha = sha_result.stdout.decode("utf-8", errors="replace").strip()
        return sha

    @staticmethod
    async def push(path: str) -> None:
        """Run ``git push``.

        Raises GitError if the push fails (e.g. no remote configured).
        """
        result = await asyncio.to_thread(_run_git, ["push"], path)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise GitError(
                f"git push failed: {stderr}",
                exit_code=result.returncode,
                stderr=stderr,
            )

    @staticmethod
    async def commit_task(project: Project, task: Task) -> str | None:
        """High-level: stage all changes, commit with conventional message, optionally push.

        Returns the commit SHA on success, or None if there was nothing to commit.
        Raises GitError if the project has no path or git operations fail.
        """
        if not project.path:
            raise GitError("Project has no local path configured")

        repo_path = project.path
        message = f"Implement task #{task.id}: {task.title}"

        await GitService.stage_all(repo_path)
        sha = await GitService.commit(repo_path, message)

        # Check if auto_push is enabled
        github_config = project.github_config or {}
        if github_config.get("auto_push", False):
            await GitService.push(repo_path)

        return sha
