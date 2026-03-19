"""Integration tests for Gemini CLI engine.

These tests invoke the real ``gemini`` CLI binary and verify that our
Process + Parser stack handles the output correctly.

Requires: ``gemini`` CLI installed and authenticated.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from codehive.engine.gemini_cli_parser import GeminiCLIParser
from codehive.engine.gemini_cli_process import GeminiCLIProcess, GeminiProcessError

from .conftest import collect_events, require_cli

PROMPT = "Reply with exactly: hello world"

# Event types that carry assistant content (streaming CLIs may use deltas only).
_CONTENT_TYPES = {"message.created", "message.delta"}


@pytest.fixture(autouse=True)
def _require_gemini_cli() -> None:
    require_cli("gemini")


@pytest.mark.asyncio
@pytest.mark.timeout(120)
class TestGeminiIntegration:
    """Tests that exercise the real Gemini CLI."""

    async def test_basic_chat(self, tmp_workdir: Path, session_id: uuid.UUID) -> None:
        """Send a simple prompt and verify we get content events."""
        process = GeminiCLIProcess(working_dir=str(tmp_workdir))
        parser = GeminiCLIParser()

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
        process = GeminiCLIProcess(working_dir=str(tmp_workdir))
        parser = GeminiCLIParser()

        events = await collect_events(process.run(PROMPT), parser, session_id)

        event_types = {e["type"] for e in events}
        # Gemini should produce at least one content-bearing event
        assert event_types & _CONTENT_TYPES, (
            f"Expected at least one content event type, got: {event_types}"
        )
        # Gemini should emit a session.started event with a session ID
        assert "session.started" in event_types, (
            f"Expected session.started in event types, got: {event_types}"
        )
        started_events = [e for e in events if e["type"] == "session.started"]
        assert started_events[0].get("gemini_session_id"), (
            "Expected non-empty gemini_session_id in session.started event"
        )

    async def test_session_resume(self, tmp_workdir: Path, session_id: uuid.UUID) -> None:
        """Send msg1, capture session_id, send msg2 with --resume, verify success."""
        process = GeminiCLIProcess(working_dir=str(tmp_workdir))
        parser = GeminiCLIParser()

        # First message: capture the gemini session ID
        events1 = await collect_events(process.run(PROMPT), parser, session_id)
        started = [e for e in events1 if e["type"] == "session.started"]
        assert started, "First run must produce a session.started event"
        gemini_session_id = started[0]["gemini_session_id"]
        assert gemini_session_id, "gemini_session_id must be non-empty"

        # Second message: resume the session (need fresh parser for state reset)
        parser2 = GeminiCLIParser()
        events2 = await collect_events(
            process.run(
                "Reply with exactly: resumed",
                resume_session_id=gemini_session_id,
            ),
            parser2,
            session_id,
        )

        # The resumed session should still produce events
        assert len(events2) >= 1, (
            f"Expected events from resumed session, got none. "
            f"First session had {len(events1)} events."
        )
        # Should have at least one content event
        content_events = [e for e in events2 if e["type"] in _CONTENT_TYPES]
        assert len(content_events) >= 1, (
            f"Expected content events from resumed session, got types: "
            f"{[e['type'] for e in events2]}"
        )

    async def test_error_handling(self, tmp_workdir: Path, session_id: uuid.UUID) -> None:
        """Invoke with invalid flags and verify graceful error handling."""
        process = GeminiCLIProcess(
            working_dir=str(tmp_workdir),
            extra_flags=["--nonexistent-flag-xyz"],
        )

        with pytest.raises((GeminiProcessError, Exception)):
            async for _line in process.run(PROMPT):
                pass
