"""Tests for ClaudeCodeEngine adapter.

All tests use mocked subprocess -- no real ``claude`` CLI invocation.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codehive.engine.base import EngineAdapter
from codehive.engine.claude_code_engine import ClaudeCodeEngine
from codehive.execution.diff import DiffService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SESSION_ID = uuid.uuid4()


def _make_mock_process(
    returncode: int | None = None,
    stdout_lines: list[bytes] | None = None,
    stderr_data: bytes = b"",
) -> MagicMock:
    """Create a mock asyncio.subprocess.Process."""
    proc = MagicMock()
    proc.returncode = returncode

    # stdin
    proc.stdin = MagicMock()
    proc.stdin.write = MagicMock()
    proc.stdin.drain = AsyncMock()

    # stdout -- returns lines one at a time, then empty (EOF)
    if stdout_lines is None:
        stdout_lines = []
    line_iter = iter(stdout_lines + [b""])
    proc.stdout = MagicMock()
    proc.stdout.readline = AsyncMock(side_effect=lambda: next(line_iter))

    # stderr
    proc.stderr = MagicMock()
    proc.stderr.read = AsyncMock(return_value=stderr_data)

    # Control methods
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    proc.wait = AsyncMock()

    return proc


async def _collect_events(aiter: Any) -> list[dict]:
    """Collect all events from an async iterator."""
    events: list[dict] = []
    async for event in aiter:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Unit: Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Verify ClaudeCodeEngine satisfies the EngineAdapter protocol."""

    def test_isinstance_check(self) -> None:
        """ClaudeCodeEngine is recognised as an EngineAdapter."""
        engine = ClaudeCodeEngine(diff_service=DiffService())
        assert isinstance(engine, EngineAdapter)

    def test_all_protocol_methods_exist(self) -> None:
        """All 8 protocol methods exist and are callable."""
        engine = ClaudeCodeEngine(diff_service=DiffService())
        methods = [
            "create_session",
            "send_message",
            "start_task",
            "pause",
            "resume",
            "approve_action",
            "reject_action",
            "get_diff",
        ]
        for method_name in methods:
            method = getattr(engine, method_name, None)
            assert method is not None, f"Missing method: {method_name}"
            assert callable(method), f"Method not callable: {method_name}"


# ---------------------------------------------------------------------------
# Unit: create_session
# ---------------------------------------------------------------------------


class TestCreateSession:
    """Tests for ClaudeCodeEngine.create_session."""

    @pytest.mark.asyncio
    async def test_create_session_spawns_process(self) -> None:
        """create_session spawns a ClaudeCodeProcess."""
        proc = _make_mock_process(returncode=None)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)

        assert SESSION_ID in engine._sessions
        assert engine._sessions[SESSION_ID].process is not None

    @pytest.mark.asyncio
    async def test_create_session_passes_working_dir(self) -> None:
        """create_session passes project_root as working_dir."""
        proc = _make_mock_process(returncode=None)
        engine = ClaudeCodeEngine(
            diff_service=DiffService(),
            working_dir="/home/user/project",
        )

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            await engine.create_session(SESSION_ID)

            kwargs = mock_exec.call_args[1]
            assert kwargs["cwd"] == "/home/user/project"

    @pytest.mark.asyncio
    async def test_create_session_duplicate_replaces(self) -> None:
        """Calling create_session twice with the same ID replaces the old session."""
        proc1 = _make_mock_process(returncode=None)
        proc2 = _make_mock_process(returncode=None)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        procs = iter([proc1, proc2])

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=lambda *a, **kw: next(procs)),
        ):
            await engine.create_session(SESSION_ID)
            await engine.create_session(SESSION_ID)

        # Old process should have been stopped
        proc1.terminate.assert_called_once()
        assert SESSION_ID in engine._sessions


# ---------------------------------------------------------------------------
# Unit: send_message
# ---------------------------------------------------------------------------


class TestSendMessage:
    """Tests for ClaudeCodeEngine.send_message."""

    @pytest.mark.asyncio
    async def test_send_message_yields_events(self) -> None:
        """send_message yields parsed codehive events from stdout."""
        stream_lines = [
            json.dumps({"type": "assistant", "content": "Hello!"}).encode() + b"\n",
            json.dumps(
                {"type": "tool_use", "name": "read_file", "input": {"path": "foo.py"}}
            ).encode()
            + b"\n",
            json.dumps({"type": "tool_result", "name": "read_file", "content": "contents"}).encode()
            + b"\n",
        ]
        proc = _make_mock_process(returncode=None, stdout_lines=stream_lines)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "Hello"))

        assert len(events) == 3
        assert events[0]["type"] == "message.created"
        assert events[0]["content"] == "Hello!"
        assert events[1]["type"] == "tool.call.started"
        assert events[2]["type"] == "tool.call.finished"

    @pytest.mark.asyncio
    async def test_send_message_events_have_required_keys(self) -> None:
        """Each yielded event has at least 'type' and 'session_id' keys."""
        stream_lines = [
            json.dumps({"type": "assistant", "content": "Test"}).encode() + b"\n",
        ]
        proc = _make_mock_process(returncode=None, stdout_lines=stream_lines)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "Test"))

        for evt in events:
            assert "type" in evt
            assert "session_id" in evt
            assert evt["session_id"] == str(SESSION_ID)

    @pytest.mark.asyncio
    async def test_send_message_nonexistent_session_raises(self) -> None:
        """send_message on a non-existent session raises KeyError."""
        engine = ClaudeCodeEngine(diff_service=DiffService())
        with pytest.raises(KeyError, match="not found"):
            await _collect_events(engine.send_message(uuid.uuid4(), "hello"))

    @pytest.mark.asyncio
    async def test_send_message_process_crash(self) -> None:
        """If the process crashes mid-stream, a session.failed event is yielded."""
        proc = _make_mock_process(
            returncode=1,
            stdout_lines=[],
            stderr_data=b"Segmentation fault",
        )
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "go"))

        assert len(events) == 1
        assert events[0]["type"] == "session.failed"
        assert events[0]["session_id"] == str(SESSION_ID)
        assert "Segmentation fault" in events[0]["error"]


# ---------------------------------------------------------------------------
# Unit: pause / resume
# ---------------------------------------------------------------------------


class TestPauseResume:
    """Tests for ClaudeCodeEngine.pause and resume."""

    @pytest.mark.asyncio
    async def test_pause_marks_session_paused(self) -> None:
        """pause() sets the paused flag on the session."""
        proc = _make_mock_process(returncode=None)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            await engine.pause(SESSION_ID)

        assert engine._sessions[SESSION_ID].paused is True

    @pytest.mark.asyncio
    async def test_resume_clears_pause(self) -> None:
        """resume() clears the paused flag."""
        proc = _make_mock_process(returncode=None)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            await engine.pause(SESSION_ID)
            await engine.resume(SESSION_ID)

        assert engine._sessions[SESSION_ID].paused is False

    @pytest.mark.asyncio
    async def test_send_message_while_paused_yields_paused_event(self) -> None:
        """send_message while paused yields session.paused and stops."""
        proc = _make_mock_process(returncode=None)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            await engine.pause(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "hello"))

        assert len(events) == 1
        assert events[0]["type"] == "session.paused"
        assert events[0]["session_id"] == str(SESSION_ID)


# ---------------------------------------------------------------------------
# Unit: approve_action / reject_action
# ---------------------------------------------------------------------------


class TestApproveReject:
    """Tests for approve_action and reject_action."""

    @pytest.mark.asyncio
    async def test_approve_action(self) -> None:
        """approve_action marks a pending action as approved."""
        proc = _make_mock_process(returncode=None)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            # Manually add a pending action
            engine._sessions[SESSION_ID].pending_actions["act-1"] = {"status": "pending"}
            await engine.approve_action(SESSION_ID, "act-1")

        assert engine._sessions[SESSION_ID].pending_actions["act-1"]["approved"] is True

    @pytest.mark.asyncio
    async def test_reject_action(self) -> None:
        """reject_action marks a pending action as rejected."""
        proc = _make_mock_process(returncode=None)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            engine._sessions[SESSION_ID].pending_actions["act-2"] = {"status": "pending"}
            await engine.reject_action(SESSION_ID, "act-2")

        assert engine._sessions[SESSION_ID].pending_actions["act-2"]["rejected"] is True


# ---------------------------------------------------------------------------
# Unit: get_diff
# ---------------------------------------------------------------------------


class TestGetDiff:
    """Tests for ClaudeCodeEngine.get_diff."""

    @pytest.mark.asyncio
    async def test_get_diff_returns_tracked_changes(self) -> None:
        """get_diff returns diffs tracked by DiffService."""
        diff_service = DiffService()
        diff_service.track_change(str(SESSION_ID), "src/main.py", "--- a\n+++ b\n+new line")

        engine = ClaudeCodeEngine(diff_service=diff_service)
        result = await engine.get_diff(SESSION_ID)

        assert isinstance(result, dict)
        assert "src/main.py" in result
        assert "+new line" in result["src/main.py"]

    @pytest.mark.asyncio
    async def test_get_diff_empty_when_no_changes(self) -> None:
        """get_diff returns empty dict when there are no tracked changes."""
        engine = ClaudeCodeEngine(diff_service=DiffService())
        result = await engine.get_diff(SESSION_ID)
        assert result == {}


# ---------------------------------------------------------------------------
# Unit: start_task
# ---------------------------------------------------------------------------


class TestStartTask:
    """Tests for ClaudeCodeEngine.start_task."""

    @pytest.mark.asyncio
    async def test_start_task_delegates_to_send_message(self) -> None:
        """start_task sends task instructions via send_message."""
        stream_lines = [
            json.dumps({"type": "assistant", "content": "Task done."}).encode() + b"\n",
        ]
        proc = _make_mock_process(returncode=None, stdout_lines=stream_lines)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            task_id = uuid.uuid4()
            events = await _collect_events(
                engine.start_task(SESSION_ID, task_id, task_instructions="Do the thing")
            )

        assert len(events) == 1
        assert events[0]["type"] == "message.created"
        assert events[0]["content"] == "Task done."

        # Verify the message was actually sent to the process
        proc.stdin.write.assert_called_once()
        written = proc.stdin.write.call_args[0][0]
        payload = json.loads(written.decode().strip())
        assert payload["content"] == "Do the thing"


# ---------------------------------------------------------------------------
# Unit: cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    """Tests for session cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_session_stops_process(self) -> None:
        """cleanup_session stops the process and removes state."""
        proc = _make_mock_process(returncode=None)

        async def fake_wait():
            proc.returncode = 0

        proc.wait = AsyncMock(side_effect=fake_wait)

        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            await engine.cleanup_session(SESSION_ID)

        assert SESSION_ID not in engine._sessions
        proc.terminate.assert_called_once()


# ---------------------------------------------------------------------------
# Integration: Engine selection in routes
# ---------------------------------------------------------------------------


class TestEngineSelection:
    """Tests for _build_engine engine type routing."""

    @pytest.mark.asyncio
    async def test_build_engine_returns_claude_code_engine(self) -> None:
        """_build_engine returns ClaudeCodeEngine for 'claude_code'."""
        from codehive.api.routes.sessions import _build_engine

        engine = await _build_engine({"project_root": "/tmp"}, engine_type="claude_code")
        assert isinstance(engine, ClaudeCodeEngine)

    @pytest.mark.asyncio
    async def test_build_engine_returns_native_engine(self) -> None:
        """_build_engine returns ZaiEngine for 'native' with zai provider."""
        from codehive.api.routes.sessions import _build_engine
        from codehive.engine.zai_engine import ZaiEngine

        with patch.dict(
            "os.environ",
            {"CODEHIVE_ZAI_API_KEY": "test-key"},
        ):
            engine = await _build_engine(
                {"project_root": "/tmp", "provider": "zai"}, engine_type="native"
            )
            assert isinstance(engine, ZaiEngine)

    @pytest.mark.asyncio
    async def test_build_engine_unknown_raises_400(self) -> None:
        """_build_engine raises HTTPException 400 for unknown engine type."""
        from fastapi import HTTPException

        from codehive.api.routes.sessions import _build_engine

        with pytest.raises(HTTPException) as exc_info:
            await _build_engine({}, engine_type="unknown_engine")
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Integration: Process + Parser + Engine pipeline
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """End-to-end: mocked stream-json through ClaudeCodeEngine.send_message."""

    @pytest.mark.asyncio
    async def test_full_pipeline_events(self) -> None:
        """Feed mocked stream-json and verify correct codehive events end-to-end."""
        stream_lines = [
            json.dumps({"type": "assistant", "content": "Let me help you."}).encode() + b"\n",
            json.dumps(
                {"type": "tool_use", "name": "read_file", "input": {"path": "foo.py"}}
            ).encode()
            + b"\n",
            json.dumps(
                {"type": "tool_result", "name": "read_file", "content": "file contents"}
            ).encode()
            + b"\n",
            json.dumps(
                {"type": "assistant", "content": [{"type": "text", "text": "Done!"}]}
            ).encode()
            + b"\n",
        ]
        proc = _make_mock_process(returncode=None, stdout_lines=stream_lines)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "Help me"))

        assert len(events) == 4
        assert events[0]["type"] == "message.created"
        assert events[0]["content"] == "Let me help you."
        assert events[1]["type"] == "tool.call.started"
        assert events[1]["tool_name"] == "read_file"
        assert events[2]["type"] == "tool.call.finished"
        assert events[2]["tool_name"] == "read_file"
        assert events[3]["type"] == "message.created"
        assert events[3]["content"] == "Done!"

        # All events have session_id
        for evt in events:
            assert evt["session_id"] == str(SESSION_ID)
