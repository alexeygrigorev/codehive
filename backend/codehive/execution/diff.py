"""Diff computation and per-session change tracking."""

from __future__ import annotations

import difflib
from pathlib import Path

from codehive.execution.git_ops import GitOps


class DiffService:
    """Compute unified diffs and track file changes per session."""

    def __init__(self) -> None:
        self._changes: dict[str, dict[str, str]] = {}  # session_id -> {file_path: diff_text}

    def compute_diff(
        self,
        file_path: str,
        original_content: str,
        current_content: str,
    ) -> str:
        """Compute a unified diff between original and current content.

        Args:
            file_path: The file path (used in the diff header).
            original_content: The original file contents.
            current_content: The current file contents.

        Returns:
            A unified diff string, or empty string if contents are identical.
        """
        if original_content == current_content:
            return ""
        diff_lines = difflib.unified_diff(
            original_content.splitlines(keepends=True),
            current_content.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        return "".join(diff_lines)

    def track_change(self, session_id: str, file_path: str, diff_text: str) -> None:
        """Record a file change for a session.

        Args:
            session_id: Identifier for the session.
            file_path: Path of the changed file.
            diff_text: The unified diff text for the change.
        """
        if session_id not in self._changes:
            self._changes[session_id] = {}
        self._changes[session_id][file_path] = diff_text

    def get_session_changes(self, session_id: str) -> dict[str, str]:
        """Return all tracked changes for a session.

        Args:
            session_id: Identifier for the session.

        Returns:
            Dict mapping file paths to their diff texts. Empty dict if no changes.
        """
        return dict(self._changes.get(session_id, {}))

    async def compute_repo_diff(self, repo_path: Path, base_ref: str | None = None) -> str:
        """Return the full repo diff against a base reference.

        Delegates to GitOps.diff().

        Args:
            repo_path: Path to the git repository.
            base_ref: Optional reference to diff against (e.g. ``HEAD``).

        Returns:
            The unified diff string from the repository.
        """
        git = GitOps(repo_path)
        return await git.diff(ref=base_ref)
