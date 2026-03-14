"""Sandboxed file operations: read, write, edit, list files within a project root."""

from __future__ import annotations

from pathlib import Path


class SandboxViolationError(Exception):
    """Raised when an operation attempts to access a path outside the sandbox."""


class FileOps:
    """File operations sandboxed to a project root directory.

    All path operations resolve symlinks and reject any resolved path
    that is not under the project_root.
    """

    def __init__(self, project_root: Path) -> None:
        self._root = Path(project_root).resolve()

    def _resolve_and_check(self, path: str | Path) -> Path:
        """Resolve a path relative to project_root and enforce sandbox.

        Args:
            path: Relative or absolute path to resolve.

        Returns:
            The resolved absolute path.

        Raises:
            SandboxViolationError: If the resolved path escapes the sandbox.
        """
        candidate = (self._root / path).resolve()
        if not candidate.is_relative_to(self._root):
            raise SandboxViolationError(
                f"Path '{path}' resolves to '{candidate}' which is outside "
                f"the sandbox root '{self._root}'"
            )
        return candidate

    async def read_file(self, path: str | Path) -> str:
        """Read and return the contents of a file.

        Args:
            path: File path relative to project_root.

        Returns:
            File contents as a string.

        Raises:
            SandboxViolationError: If the path escapes the sandbox.
            FileNotFoundError: If the file does not exist.
        """
        resolved = self._resolve_and_check(path)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {resolved}")
        return resolved.read_text(encoding="utf-8")

    async def write_file(self, path: str | Path, content: str) -> Path:
        """Write content to a file, creating parent directories if needed.

        Args:
            path: File path relative to project_root.
            content: String content to write.

        Returns:
            The resolved path of the written file.

        Raises:
            SandboxViolationError: If the path escapes the sandbox.
        """
        resolved = self._resolve_and_check(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return resolved

    async def edit_file(self, path: str | Path, old_text: str, new_text: str) -> str:
        """Replace the first occurrence of old_text with new_text in a file.

        Args:
            path: File path relative to project_root.
            old_text: Text to find.
            new_text: Text to replace it with.

        Returns:
            The updated file contents.

        Raises:
            SandboxViolationError: If the path escapes the sandbox.
            FileNotFoundError: If the file does not exist.
            ValueError: If old_text is not found in the file.
        """
        resolved = self._resolve_and_check(path)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {resolved}")
        content = resolved.read_text(encoding="utf-8")
        if old_text not in content:
            raise ValueError(f"Text not found in {path}: {old_text!r}")
        updated = content.replace(old_text, new_text, 1)
        resolved.write_text(updated, encoding="utf-8")
        return updated

    async def list_files(self, path: str | Path = ".", pattern: str = "*") -> list[str]:
        """List files matching a glob pattern within the sandbox.

        Args:
            path: Directory path relative to project_root.
            pattern: Glob pattern to match (e.g. ``*.py``).

        Returns:
            List of file paths relative to project_root.

        Raises:
            SandboxViolationError: If the path escapes the sandbox.
        """
        resolved = self._resolve_and_check(path)
        if not resolved.is_dir():
            raise NotADirectoryError(f"Not a directory: {resolved}")
        results: list[str] = []
        for match in resolved.glob(pattern):
            if match.is_file():
                try:
                    match_resolved = match.resolve()
                    if match_resolved.is_relative_to(self._root):
                        results.append(str(match_resolved.relative_to(self._root)))
                except (OSError, ValueError):
                    continue
        return sorted(results)
