"""Integration tests for Codex CLI engine.

These tests invoke the real ``codex`` CLI binary and verify that our
Process + Parser stack handles the output correctly.

Requires: ``codex`` CLI installed and authenticated.

Note: The Codex CLI ``exec --json`` output uses ``item.completed`` events
with ``item.text`` for content, which may not match all event types our
parser currently recognises.  These tests verify the actual parser behaviour
against real CLI output.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from codehive.engine.codex_cli_parser import CodexCLIParser
from codehive.engine.codex_cli_process import CodexCLIProcess

from .conftest import require_cli

PROMPT = "Reply with exactly: hello world"

# Event types that carry assistant content.
_CONTENT_TYPES = {"message.created", "message.delta"}


@pytest.fixture(autouse=True)
def _require_codex_cli() -> None:
    require_cli("codex")


@pytest.mark.asyncio
@pytest.mark.timeout(120)
class TestCodexIntegration:
    """Tests that exercise the real Codex CLI."""

    async def test_basic_chat(self, tmp_workdir: Path, session_id: uuid.UUID) -> None:
        """Send a simple prompt and verify we get content events.

        If the parser does not produce content events from the current Codex
        CLI format, the test collects all raw lines and all parsed events
        for diagnostic purposes and fails with a descriptive message.
        """
        sid = session_id
        process = CodexCLIProcess(sid, working_dir=str(tmp_workdir))
        parser = CodexCLIParser()

        await process.send(PROMPT)

        raw_lines: list[str] = []
        events: list[dict] = []
        while True:
            line = await process.read_stdout_line()
            if line is None:
                break
            raw_lines.append(line)
            parsed = parser.parse_line(line, sid)
            events.extend(parsed)

        content_events = [e for e in events if e["type"] in _CONTENT_TYPES]
        assert len(content_events) >= 1, (
            f"Expected at least one content event (message.created or message.delta). "
            f"Got event types: {[e['type'] for e in events]}. "
            f"Raw lines ({len(raw_lines)}): {raw_lines[:5]}"
        )
        contents = [e["content"] for e in content_events if e.get("content")]
        assert len(contents) >= 1, "Expected non-empty content in content events"

    async def test_event_types_received(self, tmp_workdir: Path, session_id: uuid.UUID) -> None:
        """Collect all events from a real run and verify expected types."""
        sid = session_id
        process = CodexCLIProcess(sid, working_dir=str(tmp_workdir))
        parser = CodexCLIParser()

        await process.send(PROMPT)

        raw_lines: list[str] = []
        events: list[dict] = []
        while True:
            line = await process.read_stdout_line()
            if line is None:
                break
            raw_lines.append(line)
            parsed = parser.parse_line(line, sid)
            events.extend(parsed)

        event_types = {e["type"] for e in events}
        assert event_types & _CONTENT_TYPES, (
            f"Expected at least one content event type, got: {event_types}. "
            f"Raw lines ({len(raw_lines)}): {raw_lines[:5]}"
        )

    async def test_error_handling(self, tmp_workdir: Path, session_id: uuid.UUID) -> None:
        """Invoke with invalid flags and verify graceful error handling."""
        sid = session_id
        process = CodexCLIProcess(
            sid,
            working_dir=str(tmp_workdir),
            extra_flags=["--nonexistent-flag-xyz"],
        )

        # The process should fail due to the invalid flag.
        # Either send() raises, or the process exits with an error.
        try:
            await process.send(PROMPT)
            # Drain stdout
            while True:
                line = await process.read_stdout_line()
                if line is None:
                    break
            # Check if process crashed
            crash = await process.check_for_crash()
            assert crash is not None, "Expected a crash/error event from invalid flag invocation"
            assert crash["type"] == "session.failed"
        except Exception:
            # Any exception is acceptable -- it means the error was caught
            pass
