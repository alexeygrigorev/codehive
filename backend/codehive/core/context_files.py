"""Detect and read context files (CLAUDE.md, .cursorrules, etc.) in a project directory."""

from __future__ import annotations

from pathlib import Path

# Maximum file size to include in scan results (1 MB).
MAX_CONTEXT_FILE_SIZE = 1_048_576

# Known context-file patterns.  Root-level files use plain names;
# directory patterns end with "/**/*" so pathlib.glob recurses.
CONTEXT_FILE_PATTERNS: list[str] = [
    # Root-level files
    "CLAUDE.md",
    "AGENTS.md",
    "agent.md",
    ".cursorrules",
    ".cursorignore",
    ".github/copilot-instructions.md",
    ".gemini",
    # Directory patterns (recursive)
    ".claude/**/*",
    ".codex/**/*",
    ".cursor/**/*",
]


def _matches_known_pattern(project_root: Path, rel: Path) -> bool:
    """Return True if *rel* would be found by any of CONTEXT_FILE_PATTERNS."""
    rel_str = str(rel)
    for pattern in CONTEXT_FILE_PATTERNS:
        if "**" in pattern:
            # Directory pattern – check prefix
            dir_prefix = pattern.split("/")[0]
            if rel.parts and rel.parts[0] == dir_prefix:
                return True
        else:
            if rel_str == pattern:
                return True
    return False


def scan_context_files(project_path: str) -> list[dict[str, str | int]]:
    """Scan *project_path* for known context files.

    Returns a list of ``{"path": "<relative>", "size": <bytes>}`` dicts.
    Files larger than ``MAX_CONTEXT_FILE_SIZE`` are excluded.
    Returns an empty list when the directory does not exist.
    """
    root = Path(project_path)
    if not root.is_dir():
        return []

    seen: set[Path] = set()
    results: list[dict[str, str | int]] = []

    for pattern in CONTEXT_FILE_PATTERNS:
        for match in root.glob(pattern):
            if not match.is_file():
                continue
            resolved = match.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)

            try:
                size = match.stat().st_size
            except OSError:
                continue

            if size > MAX_CONTEXT_FILE_SIZE:
                continue

            rel = match.relative_to(root)
            results.append({"path": str(rel), "size": size})

    # Sort by path for deterministic output
    results.sort(key=lambda r: r["path"])
    return results


def read_context_file(project_path: str, relative_path: str) -> str:
    """Read a single context file and return its text content.

    Raises:
        ValueError: if the relative_path escapes the project directory (path traversal).
        FileNotFoundError: if the file does not exist or is not in the known patterns list.
    """
    root = Path(project_path).resolve()
    target = (root / relative_path).resolve()

    # Security: prevent path traversal
    if not target.is_relative_to(root):
        raise ValueError("Path traversal detected")

    # Must match known patterns
    try:
        rel = target.relative_to(root)
    except ValueError:
        raise FileNotFoundError("File not in project directory")

    if not _matches_known_pattern(root, rel):
        raise FileNotFoundError("File is not a known context file pattern")

    if not target.is_file():
        raise FileNotFoundError("Context file not found")

    return target.read_text(encoding="utf-8")
