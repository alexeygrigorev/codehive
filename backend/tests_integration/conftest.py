"""Shared fixtures for CLI engine integration tests."""

from __future__ import annotations

import shutil
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest


def require_cli(name: str) -> None:
    """Mark the current test as ``xfail`` if *name* is not found on PATH.

    This is intended to be called inside an ``autouse`` fixture so that every
    test in a module is automatically marked when the CLI binary is missing.
    """
    if shutil.which(name) is None:
        pytest.xfail(f"CLI {name!r} not found on PATH")


@pytest.fixture()
def tmp_workdir(tmp_path: Path) -> Path:
    """Provide a temporary working directory for CLI invocations.

    Uses pytest's built-in ``tmp_path`` fixture so cleanup is automatic.
    """
    return tmp_path


@pytest.fixture()
def session_id() -> uuid.UUID:
    """Provide a stable UUID for the test session."""
    return uuid.uuid4()


async def collect_events(
    async_iter: AsyncIterator[str],
    parser: Any,
    session_id: uuid.UUID,
) -> list[dict]:
    """Drain an async line iterator through a parser and return all events.

    Args:
        async_iter: Async iterator yielding stdout lines (from a Process.run()).
        parser: A parser instance with a ``parse_line(line, session_id)`` method.
        session_id: The session UUID to pass to the parser.

    Returns:
        A flat list of all event dicts produced by the parser.
    """
    events: list[dict] = []
    async for line in async_iter:
        parsed = parser.parse_line(line, session_id)
        events.extend(parsed)
    return events
