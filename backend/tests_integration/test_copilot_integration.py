"""Integration tests for GitHub Copilot CLI engine.

These tests invoke the real ``copilot`` CLI binary and verify that our
Process + Parser stack handles the output correctly.

Requires: ``copilot`` (GitHub Copilot CLI) installed and authenticated.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from codehive.engine.copilot_cli_parser import CopilotCLIParser
from codehive.engine.copilot_cli_process import CopilotCLIProcess, CopilotProcessError

from .conftest import collect_events, require_cli

PROMPT = "Reply with exactly: hello world"

# Event types that carry assistant content (streaming CLIs may use deltas only).
_CONTENT_TYPES = {"message.created", "message.delta"}


@pytest.fixture(autouse=True)
def _require_copilot_cli() -> None:
    require_cli("copilot")


@pytest.mark.asyncio
@pytest.mark.timeout(120)
class TestCopilotIntegration:
    """Tests that exercise the real GitHub Copilot CLI."""

    async def test_basic_chat(self, tmp_workdir: Path, session_id: uuid.UUID) -> None:
        """Send a simple prompt and verify we get content events."""
        process = CopilotCLIProcess(working_dir=str(tmp_workdir))
        parser = CopilotCLIParser()

        events = await collect_events(process.run(PROMPT), parser, session_id)

        content_events = [e for e in events if e["type"] in _CONTENT_TYPES]
        assert len(content_events) >= 1, (
            f"Expected at least one content event (message.created or message.delta), "
            f"got event types: {[e['type'] for e in events]}"
        )
        contents = [e["content"] for e in content_events if e.get("content")]
        assert len(contents) >= 1, "Expected non-empty content in content events"

    async def test_event_types_received(self, tmp_workdir: Path, session_id: uuid.UUID) -> None:
        """Collect all events from a real run and verify expected types."""
        process = CopilotCLIProcess(working_dir=str(tmp_workdir))
        parser = CopilotCLIParser()

        events = await collect_events(process.run(PROMPT), parser, session_id)

        event_types = {e["type"] for e in events}
        assert event_types & _CONTENT_TYPES, (
            f"Expected at least one content event type, got: {event_types}"
        )

    async def test_error_handling(self, tmp_workdir: Path, session_id: uuid.UUID) -> None:
        """Invoke with invalid flags and verify graceful error handling."""
        process = CopilotCLIProcess(
            working_dir=str(tmp_workdir),
            extra_flags=["--nonexistent-flag-xyz"],
        )

        with pytest.raises((CopilotProcessError, Exception)):
            async for _line in process.run(PROMPT):
                pass
