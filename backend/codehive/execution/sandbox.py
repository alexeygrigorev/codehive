"""Filesystem sandbox: reusable path validation with symlink and restricted directory checks."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from codehive.execution.file_ops import SandboxViolationError


class Sandbox:
    """Validates that file paths stay within a project root.

    Provides:
    - Path escape detection (resolve + is_relative_to)
    - Symlink-in-the-middle detection (intermediate components)
    - Restricted directory blocking (e.g. .git, .env)
    - Configurable allowed/denied glob patterns
    """

    def __init__(
        self,
        root: Path,
        restricted_dirs: set[str] | None = None,
        allowed_patterns: list[str] | None = None,
        denied_patterns: list[str] | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._restricted_dirs: set[str] = (
            restricted_dirs if restricted_dirs is not None else {".git", ".env"}
        )
        self._allowed_patterns: list[str] = allowed_patterns or []
        self._denied_patterns: list[str] = denied_patterns or []

    @property
    def root(self) -> Path:
        """The resolved sandbox root directory."""
        return self._root

    def check(self, path: str | Path) -> Path:
        """Validate a path against all sandbox rules and return the resolved path.

        Args:
            path: Relative or absolute path to validate.

        Returns:
            The resolved absolute path.

        Raises:
            SandboxViolationError: If the path violates any sandbox rule.
        """
        candidate = (self._root / path).resolve()

        # Basic escape check
        if not candidate.is_relative_to(self._root):
            raise SandboxViolationError(
                f"Path '{path}' resolves to '{candidate}' which is outside "
                f"the sandbox root '{self._root}'"
            )

        # Symlink-in-the-middle check: walk each component of the raw
        # (non-resolved) path and check if any intermediate directory is a
        # symlink pointing outside the sandbox.
        self._check_intermediate_symlinks(path)

        # Restricted directory check
        rel = candidate.relative_to(self._root)
        self._check_restricted_dirs(rel)

        # Glob pattern checks
        self._check_patterns(rel)

        return candidate

    def _check_intermediate_symlinks(self, path: str | Path) -> None:
        """Detect symlinks in intermediate path components that escape the sandbox."""
        # Walk each parent starting from root downward
        parts = Path(path).parts
        current = self._root
        for part in parts:
            current = current / part
            if current.is_symlink():
                target = current.resolve()
                if not target.is_relative_to(self._root):
                    raise SandboxViolationError(
                        f"Symlink '{current}' points to '{target}' which is outside "
                        f"the sandbox root '{self._root}'"
                    )

    def _check_restricted_dirs(self, rel_path: Path) -> None:
        """Block access to restricted directories."""
        if not self._restricted_dirs:
            return
        for part in rel_path.parts:
            if part in self._restricted_dirs:
                raise SandboxViolationError(
                    f"Access to restricted directory '{part}' is not allowed"
                )

    def _check_patterns(self, rel_path: Path) -> None:
        """Apply allowed/denied glob patterns. Allowlist wins when both match."""
        rel_str = str(rel_path)

        matches_allowed = any(fnmatch.fnmatch(rel_str, pat) for pat in self._allowed_patterns)
        matches_denied = any(fnmatch.fnmatch(rel_str, pat) for pat in self._denied_patterns)

        if matches_allowed:
            # Allowlist takes precedence
            return

        if matches_denied:
            raise SandboxViolationError(f"Path '{rel_str}' matches a denied pattern")
