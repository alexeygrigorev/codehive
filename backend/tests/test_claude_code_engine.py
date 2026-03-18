"""Tests for ClaudeCodeEngine adapter (fire-and-forget model).

All tests use mocked subprocess -- no real ``claude`` CLI invocation.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codehive.engine.base import EngineAdapter
from codehive.engine.claude_code_engine import ClaudeCodeEngine, MAX_RETRIES
from codehive.execution.diff import DiffService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SESSION_ID = uuid.uuid4()


def _make_mock_process(
    returncode: int = 0,
    stdout_lines: list[bytes] | None = None,
    stderr_data: bytes = b"",
) -> MagicMock:
    """Create a mock asyncio.subprocess.Process for fire-and-forget model."""
    proc = MagicMock()
    proc.returncode = returncode

    if stdout_lines is None:
        stdout_lines = []
    line_iter = iter(stdout_lines + [b""])
    proc.stdout = MagicMock()
    proc.stdout.readline = AsyncMock(side_effect=lambda: next(line_iter))

    proc.stderr = MagicMock()
    proc.stderr.read = AsyncMock(return_value=stderr_data)

    proc.wait = AsyncMock(return_value=returncode)

    return proc


async def _collect_events(aiter: Any) -> list[dict]:
    """Collect all events from an async iterator."""
    events: list[dict] = []
    async for event in aiter:
        events.append(event)
    return events


def _system_init_line(session_id: str = "claude-sess-abc", model: str = "opus") -> bytes:
    """Build a system.init JSON line."""
    return (
        json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "session_id": session_id,
                "model": model,
            }
        ).encode()
        + b"\n"
    )


def _assistant_line(content: str = "Hello!") -> bytes:
    """Build an assistant JSON line."""
    return json.dumps({"type": "assistant", "content": content}).encode() + b"\n"


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
    async def test_create_session_initialises_state(self) -> None:
        """create_session creates internal state without spawning a subprocess."""
        engine = ClaudeCodeEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)

        assert SESSION_ID in engine._sessions
        state = engine._sessions[SESSION_ID]
        assert state.claude_session_id is None
        assert state.retry_count == 0
        assert state.paused is False

    @pytest.mark.asyncio
    async def test_create_session_duplicate_replaces(self) -> None:
        """Calling create_session twice with the same ID replaces old state."""
        engine = ClaudeCodeEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        engine._sessions[SESSION_ID].claude_session_id = "old-sess"

        await engine.create_session(SESSION_ID)
        assert engine._sessions[SESSION_ID].claude_session_id is None


# ---------------------------------------------------------------------------
# Unit: send_message
# ---------------------------------------------------------------------------


class TestSendMessage:
    """Tests for ClaudeCodeEngine.send_message (fire-and-forget)."""

    @pytest.mark.asyncio
    async def test_first_message_no_resume(self) -> None:
        """First message does not use --resume, captures session_id from system.init."""
        proc = _make_mock_process(
            returncode=0,
            stdout_lines=[_system_init_line("cs-xyz"), _assistant_line("Hi!")],
        )
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "Hello"))

        # Verify --resume was NOT used
        args = mock_exec.call_args[0]
        assert "--resume" not in args

        # session_id captured
        assert engine._sessions[SESSION_ID].claude_session_id == "cs-xyz"

        # Events yielded
        assert len(events) == 2
        assert events[0]["type"] == "session.started"
        assert events[0]["claude_session_id"] == "cs-xyz"
        assert events[1]["type"] == "message.created"
        assert events[1]["content"] == "Hi!"

    @pytest.mark.asyncio
    async def test_second_message_uses_resume(self) -> None:
        """Second message uses --resume with the stored session_id."""
        proc1 = _make_mock_process(
            returncode=0,
            stdout_lines=[_system_init_line("cs-first"), _assistant_line("First")],
        )
        proc2 = _make_mock_process(
            returncode=0,
            stdout_lines=[_assistant_line("Second")],
        )
        procs = iter([proc1, proc2])

        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=lambda *a, **kw: next(procs)),
        ) as mock_exec:
            await engine.create_session(SESSION_ID)
            await _collect_events(engine.send_message(SESSION_ID, "First msg"))
            await _collect_events(engine.send_message(SESSION_ID, "Second msg"))

        # Second call should have --resume
        second_call_args = mock_exec.call_args_list[1][0]
        assert "--resume" in second_call_args
        assert "cs-first" in second_call_args

    @pytest.mark.asyncio
    async def test_send_message_yields_events(self) -> None:
        """send_message yields parsed codehive events from stdout."""
        stream_lines = [
            _assistant_line("Hello!"),
            json.dumps(
                {"type": "tool_use", "name": "read_file", "input": {"path": "foo.py"}}
            ).encode()
            + b"\n",
            json.dumps({"type": "tool_result", "name": "read_file", "content": "contents"}).encode()
            + b"\n",
        ]
        proc = _make_mock_process(returncode=0, stdout_lines=stream_lines)
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
        proc = _make_mock_process(
            returncode=0,
            stdout_lines=[_assistant_line("Test")],
        )
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


# ---------------------------------------------------------------------------
# Unit: auto-retry on crash
# ---------------------------------------------------------------------------


class TestAutoRetry:
    """Tests for auto-retry on process crash."""

    @pytest.mark.asyncio
    async def test_crash_retries_with_resume(self) -> None:
        """On crash, engine retries with --resume and continuation prompt."""
        # First call crashes, retry succeeds
        crash_proc = _make_mock_process(
            returncode=1,
            stdout_lines=[_system_init_line("cs-crash")],
            stderr_data=b"crash",
        )
        retry_proc = _make_mock_process(
            returncode=0,
            stdout_lines=[_assistant_line("Recovered!")],
        )
        procs = iter([crash_proc, retry_proc])

        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=lambda *a, **kw: next(procs)),
        ) as mock_exec:
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "Do something"))

        # First call yielded system.init, then crashed
        # Retry call should use --resume
        retry_args = mock_exec.call_args_list[1][0]
        assert "--resume" in retry_args
        assert "cs-crash" in retry_args

        # Should include events from both first call and retry
        event_types = [e["type"] for e in events]
        assert "session.started" in event_types
        assert "message.created" in event_types

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_yields_session_failed(self) -> None:
        """After MAX_RETRIES+1 crashes, yields session.failed event."""
        # All processes crash
        procs = []
        for i in range(MAX_RETRIES + 1):
            p = _make_mock_process(
                returncode=1,
                stdout_lines=[_system_init_line(f"cs-crash-{i}")],
                stderr_data=b"crash",
            )
            procs.append(p)

        proc_iter = iter(procs)

        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=lambda *a, **kw: next(proc_iter)),
        ):
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "Go"))

        # Last event should be session.failed
        failed_events = [e for e in events if e["type"] == "session.failed"]
        assert len(failed_events) == 1
        assert "retries exhausted" in failed_events[0]["error"]

    @pytest.mark.asyncio
    async def test_crash_without_session_id_yields_failed(self) -> None:
        """If crash happens before system.init, yields session.failed (no resume possible)."""
        crash_proc = _make_mock_process(
            returncode=1,
            stdout_lines=[],  # No system.init
            stderr_data=b"immediate crash",
        )

        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=crash_proc),
        ):
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "Go"))

        failed = [e for e in events if e["type"] == "session.failed"]
        assert len(failed) == 1
        assert "no claude session ID" in failed[0]["error"]

    @pytest.mark.asyncio
    async def test_retry_resets_count_on_success(self) -> None:
        """After successful retry, retry_count is reset to 0."""
        crash_proc = _make_mock_process(
            returncode=1,
            stdout_lines=[_system_init_line("cs-1")],
            stderr_data=b"crash",
        )
        ok_proc = _make_mock_process(
            returncode=0,
            stdout_lines=[_assistant_line("OK")],
        )
        procs = iter([crash_proc, ok_proc])

        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=lambda *a, **kw: next(procs)),
        ):
            await engine.create_session(SESSION_ID)
            await _collect_events(engine.send_message(SESSION_ID, "Go"))

        assert engine._sessions[SESSION_ID].retry_count == 0


# ---------------------------------------------------------------------------
# Unit: pause / resume
# ---------------------------------------------------------------------------


class TestPauseResume:
    """Tests for ClaudeCodeEngine.pause and resume."""

    @pytest.mark.asyncio
    async def test_pause_marks_session_paused(self) -> None:
        engine = ClaudeCodeEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.pause(SESSION_ID)
        assert engine._sessions[SESSION_ID].paused is True

    @pytest.mark.asyncio
    async def test_resume_clears_pause(self) -> None:
        engine = ClaudeCodeEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.pause(SESSION_ID)
        await engine.resume(SESSION_ID)
        assert engine._sessions[SESSION_ID].paused is False

    @pytest.mark.asyncio
    async def test_send_message_while_paused_yields_paused_event(self) -> None:
        """send_message while paused yields session.paused and stops."""
        engine = ClaudeCodeEngine(diff_service=DiffService())
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
        engine = ClaudeCodeEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        engine._sessions[SESSION_ID].pending_actions["act-1"] = {"status": "pending"}
        await engine.approve_action(SESSION_ID, "act-1")
        assert engine._sessions[SESSION_ID].pending_actions["act-1"]["approved"] is True

    @pytest.mark.asyncio
    async def test_reject_action(self) -> None:
        engine = ClaudeCodeEngine(diff_service=DiffService())
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
        diff_service = DiffService()
        diff_service.track_change(str(SESSION_ID), "src/main.py", "--- a\n+++ b\n+new line")
        engine = ClaudeCodeEngine(diff_service=diff_service)
        result = await engine.get_diff(SESSION_ID)
        assert isinstance(result, dict)
        assert "src/main.py" in result
        assert "+new line" in result["src/main.py"]

    @pytest.mark.asyncio
    async def test_get_diff_empty_when_no_changes(self) -> None:
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
        proc = _make_mock_process(
            returncode=0,
            stdout_lines=[_assistant_line("Task done.")],
        )
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            await engine.create_session(SESSION_ID)
            task_id = uuid.uuid4()
            events = await _collect_events(
                engine.start_task(SESSION_ID, task_id, task_instructions="Do the thing")
            )

        assert len(events) == 1
        assert events[0]["type"] == "message.created"
        assert events[0]["content"] == "Task done."

        # Verify the message was passed as -p argument
        args = mock_exec.call_args[0]
        assert "Do the thing" in args


# ---------------------------------------------------------------------------
# Unit: cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    """Tests for session cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_session_removes_state(self) -> None:
        """cleanup_session removes the session state (no process to stop)."""
        engine = ClaudeCodeEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.cleanup_session(SESSION_ID)
        assert SESSION_ID not in engine._sessions


# ---------------------------------------------------------------------------
# Unit: multiple independent sessions
# ---------------------------------------------------------------------------


class TestMultipleSessions:
    """Tests for independent session tracking."""

    @pytest.mark.asyncio
    async def test_independent_sessions(self) -> None:
        """Two sessions track separate claude_session_ids."""
        sid_a = uuid.uuid4()
        sid_b = uuid.uuid4()

        proc_a = _make_mock_process(
            returncode=0,
            stdout_lines=[_system_init_line("cs-A"), _assistant_line("A")],
        )
        proc_b = _make_mock_process(
            returncode=0,
            stdout_lines=[_system_init_line("cs-B"), _assistant_line("B")],
        )
        procs = iter([proc_a, proc_b])

        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=lambda *a, **kw: next(procs)),
        ):
            await engine.create_session(sid_a)
            await engine.create_session(sid_b)
            await _collect_events(engine.send_message(sid_a, "A"))
            await _collect_events(engine.send_message(sid_b, "B"))

        assert engine._sessions[sid_a].claude_session_id == "cs-A"
        assert engine._sessions[sid_b].claude_session_id == "cs-B"


# ---------------------------------------------------------------------------
# Integration: Engine selection in routes
# ---------------------------------------------------------------------------


class TestEngineSelection:
    """Tests for _build_engine engine type routing."""

    @pytest.mark.asyncio
    async def test_build_engine_returns_claude_code_engine(self) -> None:
        from codehive.api.routes.sessions import _build_engine

        engine = await _build_engine({"project_root": "/tmp"}, engine_type="claude_code")
        assert isinstance(engine, ClaudeCodeEngine)

    @pytest.mark.asyncio
    async def test_build_engine_returns_native_engine(self) -> None:
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
        from fastapi import HTTPException

        from codehive.api.routes.sessions import _build_engine

        with pytest.raises(HTTPException) as exc_info:
            await _build_engine({}, engine_type="unknown_engine")
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Integration: Full pipeline (mocked subprocess -> engine -> events)
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """End-to-end: mocked stream-json through ClaudeCodeEngine.send_message."""

    @pytest.mark.asyncio
    async def test_full_pipeline_events(self) -> None:
        """Feed mocked stream-json and verify correct codehive events end-to-end."""
        stream_lines = [
            _system_init_line("cs-pipe"),
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
        proc = _make_mock_process(returncode=0, stdout_lines=stream_lines)
        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "Help me"))

        assert len(events) == 5
        assert events[0]["type"] == "session.started"
        assert events[0]["claude_session_id"] == "cs-pipe"
        assert events[1]["type"] == "message.created"
        assert events[1]["content"] == "Let me help you."
        assert events[2]["type"] == "tool.call.started"
        assert events[2]["tool_name"] == "read_file"
        assert events[3]["type"] == "tool.call.finished"
        assert events[3]["tool_name"] == "read_file"
        assert events[4]["type"] == "message.created"
        assert events[4]["content"] == "Done!"

        for evt in events:
            assert evt["session_id"] == str(SESSION_ID)

    @pytest.mark.asyncio
    async def test_sse_pipeline_with_error(self) -> None:
        """Error events from crashed subprocess appear in the event stream."""
        crash_proc = _make_mock_process(
            returncode=1,
            stdout_lines=[],
            stderr_data=b"Segmentation fault",
        )

        engine = ClaudeCodeEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=crash_proc),
        ):
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "go"))

        # No session_id means can't resume, so session.failed
        assert any(e["type"] == "session.failed" for e in events)
