"""Git CLI wrapper: status, diff, commit, checkout, branch, log."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileStatus:
    """A single file's git status."""

    path: str
    status: str  # "modified", "added", "deleted", "untracked", "renamed", etc.


@dataclass
class CommitInfo:
    """Summary of a single git commit."""

    sha: str
    message: str
    author: str
    timestamp: str


class GitOpsError(Exception):
    """Raised when a git operation fails."""


class GitOps:
    """Git operations that shell out to the git CLI.

    Args:
        repo_path: Path to the git repository root.
    """

    def __init__(self, repo_path: Path) -> None:
        self._repo = Path(repo_path)

    async def _run(self, *args: str) -> tuple[str, str]:
        """Run a git command and return (stdout, stderr).

        Raises:
            GitOpsError: If the command exits with a non-zero code.
        """
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._repo,
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise GitOpsError(f"git {' '.join(args)} failed (rc={process.returncode}): {stderr}")
        return stdout, stderr

    async def status(self) -> list[FileStatus]:
        """Return parsed git status as a list of FileStatus entries."""
        stdout, _ = await self._run("status", "--porcelain=v1", "-uall")
        results: list[FileStatus] = []
        status_map = {
            "M": "modified",
            "A": "added",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "?": "untracked",
        }
        for line in stdout.splitlines():
            if len(line) < 4:
                continue
            xy = line[:2]
            file_path = line[3:].strip()
            # Use index status (first char) if set, otherwise working tree (second char)
            code = xy[0] if xy[0].strip() else xy[1]
            status_label = status_map.get(code, "modified")
            results.append(FileStatus(path=file_path, status=status_label))
        return results

    async def diff(self, ref: str | None = None) -> str:
        """Return unified diff string.

        Args:
            ref: Optional reference to diff against (e.g. ``HEAD``, a SHA, branch name).
                 Defaults to unstaged changes.

        Returns:
            The unified diff as a string.
        """
        args = ["diff"]
        if ref is not None:
            args.append(ref)
        stdout, _ = await self._run(*args)
        return stdout

    async def commit(self, message: str, paths: list[str] | None = None) -> str:
        """Stage paths and commit.

        Args:
            message: Commit message.
            paths: Specific paths to stage. If None, stages all changes.

        Returns:
            The new commit SHA.
        """
        if paths:
            await self._run("add", "--", *paths)
        else:
            await self._run("add", "-A")
        await self._run("commit", "-m", message)
        stdout, _ = await self._run("rev-parse", "HEAD")
        return stdout.strip()

    async def checkout(self, ref: str) -> None:
        """Check out a branch or commit.

        Args:
            ref: Branch name, tag, or commit SHA to check out.
        """
        await self._run("checkout", ref)

    async def branch(self, name: str) -> None:
        """Create a new branch.

        Args:
            name: Name for the new branch.
        """
        await self._run("branch", name)

    async def push(self, remote: str = "origin", branch: str = "main") -> str:
        """Push commits to a remote.

        Args:
            remote: Remote name (default ``origin``).
            branch: Branch name (default ``main``).

        Returns:
            stdout from the git push command.

        Raises:
            GitOpsError: If the push fails.
        """
        stdout, _ = await self._run("push", remote, branch)
        return stdout

    async def log(self, n: int = 10) -> list[CommitInfo]:
        """Return the last N commits.

        Args:
            n: Number of commits to return.

        Returns:
            List of CommitInfo objects.
        """
        stdout, _ = await self._run(
            "log",
            f"-{n}",
            "--format=%H%n%s%n%an%n%aI%n---",
        )
        commits: list[CommitInfo] = []
        entries = stdout.strip().split("---\n")
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            lines = entry.splitlines()
            if len(lines) >= 4:
                commits.append(
                    CommitInfo(
                        sha=lines[0],
                        message=lines[1],
                        author=lines[2],
                        timestamp=lines[3],
                    )
                )
        return commits
