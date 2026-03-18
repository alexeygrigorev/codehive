"""Tests for CodexCLIEngine, CodexCLIProcess, and CodexCLIParser.

All tests use mocked subprocess -- no real ``codex`` CLI invocation.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codehive.engine.base import EngineAdapter
from codehive.engine.codex_cli_engine import CodexCLIEngine
from codehive.engine.codex_cli_parser import CodexCLIParser
from codehive.engine.codex_cli_process import CodexCLIProcess
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
# Unit: CodexCLIProcess
# ---------------------------------------------------------------------------


class TestCodexCLIProcess:
    """Unit tests for CodexCLIProcess."""

    def test_build_command_default_flags(self) -> None:
        """_build_command returns correct command with default flags."""
        p = CodexCLIProcess(session_id=SESSION_ID)
        cmd = p._build_command("hello world")
        assert cmd[0] == "codex"
        assert "exec" in cmd
        assert "--json" in cmd
        assert "--full-auto" in cmd
        assert cmd[-1] == "hello world"

    def test_build_command_includes_model(self) -> None:
        """_build_command includes --model flag."""
        p = CodexCLIProcess(session_id=SESSION_ID, model="o3-mini")
        cmd = p._build_command("test")
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "o3-mini"

    def test_build_command_includes_working_dir(self) -> None:
        """_build_command includes -C flag when working_dir is set."""
        p = CodexCLIProcess(session_id=SESSION_ID, working_dir="/home/user/project")
        cmd = p._build_command("test")
        idx = cmd.index("-C")
        assert cmd[idx + 1] == "/home/user/project"

    def test_build_command_includes_extra_flags(self) -> None:
        """_build_command includes extra_flags."""
        p = CodexCLIProcess(
            session_id=SESSION_ID,
            extra_flags=["--sandbox", "-c", "some=value"],
        )
        cmd = p._build_command("test")
        assert "--sandbox" in cmd
        assert "-c" in cmd
        assert "some=value" in cmd

    def test_build_command_no_model_flag_when_empty(self) -> None:
        """_build_command skips --model when model is empty string."""
        p = CodexCLIProcess(session_id=SESSION_ID, model="")
        cmd = p._build_command("test")
        assert "--model" not in cmd

    @pytest.mark.asyncio
    async def test_send_creates_subprocess(self) -> None:
        """send() creates an async subprocess with correct args."""
        proc = _make_mock_process(returncode=None)

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = CodexCLIProcess(session_id=SESSION_ID)
            await p.send("Hello codex")

            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert args[0] == "codex"
            assert "exec" in args
            assert "--json" in args
            assert "--full-auto" in args
            assert args[-1] == "Hello codex"

    @pytest.mark.asyncio
    async def test_read_stdout_line_returns_decoded(self) -> None:
        """read_stdout_line returns decoded lines."""
        line_data = json.dumps({"type": "message", "content": "hi"})
        proc = _make_mock_process(
            returncode=None,
            stdout_lines=[f"{line_data}\n".encode()],
        )

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = CodexCLIProcess(session_id=SESSION_ID)
            await p.send("test")

            line = await p.read_stdout_line()
            assert line == line_data

    @pytest.mark.asyncio
    async def test_read_stdout_line_returns_none_on_eof(self) -> None:
        """read_stdout_line returns None on EOF."""
        proc = _make_mock_process(returncode=None, stdout_lines=[])

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = CodexCLIProcess(session_id=SESSION_ID)
            await p.send("test")

            eof = await p.read_stdout_line()
            assert eof is None

    @pytest.mark.asyncio
    async def test_check_for_crash_returns_session_failed(self) -> None:
        """check_for_crash returns session.failed on non-zero exit."""
        proc = _make_mock_process(returncode=1, stderr_data=b"Error occurred")

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = CodexCLIProcess(session_id=SESSION_ID)
            await p.send("test")

            event = await p.check_for_crash()
            assert event is not None
            assert event["type"] == "session.failed"
            assert event["session_id"] == str(SESSION_ID)
            assert event["exit_code"] == 1
            assert "Error occurred" in event["error"]

    @pytest.mark.asyncio
    async def test_check_for_crash_returns_none_when_running(self) -> None:
        """check_for_crash returns None when process is still running."""
        proc = _make_mock_process(returncode=None)

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = CodexCLIProcess(session_id=SESSION_ID)
            await p.send("test")

            assert await p.check_for_crash() is None

    @pytest.mark.asyncio
    async def test_check_for_crash_returns_none_on_clean_exit(self) -> None:
        """check_for_crash returns None when process exits with code 0."""
        proc = _make_mock_process(returncode=0)

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = CodexCLIProcess(session_id=SESSION_ID)
            await p.send("test")

            assert await p.check_for_crash() is None

    @pytest.mark.asyncio
    async def test_stop_terminates_process(self) -> None:
        """stop() terminates the subprocess gracefully."""
        proc = _make_mock_process(returncode=None)

        async def fake_wait():
            proc.returncode = 0

        proc.wait = AsyncMock(side_effect=fake_wait)

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = CodexCLIProcess(session_id=SESSION_ID)
            await p.send("test")

            assert p.is_alive()
            await p.stop()

            proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_alive_not_started(self) -> None:
        """is_alive returns False before send()."""
        p = CodexCLIProcess(session_id=SESSION_ID)
        assert p.is_alive() is False


# ---------------------------------------------------------------------------
# Unit: CodexCLIParser
# ---------------------------------------------------------------------------


class TestCodexCLIParser:
    """Unit tests for CodexCLIParser.parse_line()."""

    @pytest.fixture
    def parser(self) -> CodexCLIParser:
        return CodexCLIParser()

    def test_parse_agent_text_message(self, parser: CodexCLIParser) -> None:
        """Parse a message event into message.created."""
        line = json.dumps({"type": "message", "content": "Hello from Codex!"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        evt = events[0]
        assert evt["type"] == "message.created"
        assert evt["role"] == "assistant"
        assert evt["content"] == "Hello from Codex!"
        assert evt["session_id"] == str(SESSION_ID)

    def test_parse_tool_call_started(self, parser: CodexCLIParser) -> None:
        """Parse a command event into tool.call.started."""
        line = json.dumps(
            {
                "type": "command",
                "name": "run_shell",
                "input": {"command": "ls -la"},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        evt = events[0]
        assert evt["type"] == "tool.call.started"
        assert evt["tool_name"] == "run_shell"
        assert evt["tool_input"] == {"command": "ls -la"}
        assert evt["session_id"] == str(SESSION_ID)

    def test_parse_tool_result_finished(self, parser: CodexCLIParser) -> None:
        """Parse a command_result event into tool.call.finished."""
        line = json.dumps(
            {
                "type": "command_result",
                "name": "run_shell",
                "output": "file1.py\nfile2.py",
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        evt = events[0]
        assert evt["type"] == "tool.call.finished"
        assert evt["tool_name"] == "run_shell"
        assert evt["result"] == "file1.py\nfile2.py"
        assert evt["session_id"] == str(SESSION_ID)

    def test_parse_error_event(self, parser: CodexCLIParser) -> None:
        """Parse an error event into session.error."""
        line = json.dumps({"type": "error", "error": "Rate limit exceeded"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "session.error"
        assert events[0]["error"] == "Rate limit exceeded"
        assert events[0]["session_id"] == str(SESSION_ID)

    def test_parse_blank_line(self, parser: CodexCLIParser) -> None:
        """Blank lines return empty list."""
        assert parser.parse_line("", SESSION_ID) == []
        assert parser.parse_line("   \n  ", SESSION_ID) == []

    def test_parse_malformed_json(self, parser: CodexCLIParser) -> None:
        """Malformed JSON returns empty list, no exception."""
        events = parser.parse_line("this is not json {{{", SESSION_ID)
        assert events == []

    def test_parse_unrecognized_type(self, parser: CodexCLIParser) -> None:
        """Unrecognised event type returns empty list."""
        line = json.dumps({"type": "some_future_type", "data": "foo"})
        events = parser.parse_line(line, SESSION_ID)
        assert events == []

    def test_all_events_include_session_id(self, parser: CodexCLIParser) -> None:
        """Every event includes session_id and type keys."""
        lines = [
            json.dumps({"type": "message", "content": "hi"}),
            json.dumps({"type": "command", "name": "x", "input": {}}),
            json.dumps({"type": "command_result", "name": "x", "output": "ok"}),
            json.dumps({"type": "error", "error": "bad"}),
        ]
        for line in lines:
            for evt in parser.parse_line(line, SESSION_ID):
                assert "type" in evt, f"Missing 'type' in event from: {line}"
                assert "session_id" in evt, f"Missing 'session_id' in event from: {line}"
                assert evt["session_id"] == str(SESSION_ID)

    def test_parse_file_change_event(self, parser: CodexCLIParser) -> None:
        """Parse a file_change event into file.changed."""
        line = json.dumps({"type": "file_change", "path": "src/main.py"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "file.changed"
        assert events[0]["path"] == "src/main.py"

    def test_parse_non_dict_json(self, parser: CodexCLIParser) -> None:
        """A JSON array (non-object) returns empty list."""
        events = parser.parse_line("[1, 2, 3]", SESSION_ID)
        assert events == []

    def test_parse_text_delta(self, parser: CodexCLIParser) -> None:
        """text_delta event is parsed as message.delta."""
        line = json.dumps({"type": "text_delta", "delta": "streaming chunk"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.delta"
        assert events[0]["content"] == "streaming chunk"

    def test_parse_assistant_type(self, parser: CodexCLIParser) -> None:
        """The 'assistant' type also maps to message.created."""
        line = json.dumps({"type": "assistant", "content": "text from assistant"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.created"
        assert events[0]["content"] == "text from assistant"

    def test_parse_tool_result_with_file_change(self, parser: CodexCLIParser) -> None:
        """Tool result for edit_file emits both finished and file.changed."""
        line = json.dumps(
            {
                "type": "tool_result",
                "name": "edit_file",
                "output": "File edited",
                "path": "src/main.py",
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 2
        assert events[0]["type"] == "tool.call.finished"
        assert events[1]["type"] == "file.changed"
        assert events[1]["path"] == "src/main.py"


# ---------------------------------------------------------------------------
# Unit: CodexCLIEngine - Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Verify CodexCLIEngine satisfies the EngineAdapter protocol."""

    def test_isinstance_check(self) -> None:
        """CodexCLIEngine is recognised as an EngineAdapter."""
        engine = CodexCLIEngine(diff_service=DiffService())
        assert isinstance(engine, EngineAdapter)

    def test_all_protocol_methods_exist(self) -> None:
        """All 8 protocol methods exist and are callable."""
        engine = CodexCLIEngine(diff_service=DiffService())
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
# Unit: CodexCLIEngine - create_session
# ---------------------------------------------------------------------------


class TestCreateSession:
    """Tests for CodexCLIEngine.create_session."""

    @pytest.mark.asyncio
    async def test_create_session_initializes_state(self) -> None:
        """create_session initializes session state."""
        engine = CodexCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        assert SESSION_ID in engine._sessions
        assert engine._sessions[SESSION_ID].paused is False

    @pytest.mark.asyncio
    async def test_create_session_duplicate_replaces(self) -> None:
        """Calling create_session twice replaces the old session state."""
        engine = CodexCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        state1 = engine._sessions[SESSION_ID]
        await engine.create_session(SESSION_ID)
        state2 = engine._sessions[SESSION_ID]
        assert state1 is not state2


# ---------------------------------------------------------------------------
# Unit: CodexCLIEngine - send_message
# ---------------------------------------------------------------------------


class TestSendMessage:
    """Tests for CodexCLIEngine.send_message."""

    @pytest.mark.asyncio
    async def test_send_message_yields_events(self) -> None:
        """send_message yields parsed codehive events from subprocess stdout."""
        stream_lines = [
            json.dumps({"type": "message", "content": "Hello!"}).encode() + b"\n",
            json.dumps(
                {"type": "command", "name": "read_file", "input": {"path": "foo.py"}}
            ).encode()
            + b"\n",
            json.dumps(
                {"type": "command_result", "name": "read_file", "output": "contents"}
            ).encode()
            + b"\n",
        ]
        proc = _make_mock_process(returncode=None, stdout_lines=stream_lines)
        engine = CodexCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
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
            json.dumps({"type": "message", "content": "Test"}).encode() + b"\n",
        ]
        proc = _make_mock_process(returncode=None, stdout_lines=stream_lines)
        engine = CodexCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
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
        engine = CodexCLIEngine(diff_service=DiffService())
        with pytest.raises(KeyError, match="not found"):
            await _collect_events(engine.send_message(uuid.uuid4(), "hello"))

    @pytest.mark.asyncio
    async def test_send_message_process_crash(self) -> None:
        """If the process crashes, a session.failed event is yielded."""
        proc = _make_mock_process(
            returncode=1,
            stdout_lines=[],
            stderr_data=b"Segmentation fault",
        )
        engine = CodexCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "go"))

        assert len(events) == 1
        assert events[0]["type"] == "session.failed"
        assert events[0]["session_id"] == str(SESSION_ID)
        assert "Segmentation fault" in events[0]["error"]


# ---------------------------------------------------------------------------
# Unit: CodexCLIEngine - pause / resume
# ---------------------------------------------------------------------------


class TestPauseResume:
    """Tests for pause and resume."""

    @pytest.mark.asyncio
    async def test_pause_marks_session_paused(self) -> None:
        """pause() sets the paused flag."""
        engine = CodexCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.pause(SESSION_ID)
        assert engine._sessions[SESSION_ID].paused is True

    @pytest.mark.asyncio
    async def test_resume_clears_pause(self) -> None:
        """resume() clears the paused flag."""
        engine = CodexCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.pause(SESSION_ID)
        await engine.resume(SESSION_ID)
        assert engine._sessions[SESSION_ID].paused is False

    @pytest.mark.asyncio
    async def test_send_message_while_paused_yields_paused_event(self) -> None:
        """send_message while paused yields session.paused and stops."""
        engine = CodexCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.pause(SESSION_ID)
        events = await _collect_events(engine.send_message(SESSION_ID, "hello"))

        assert len(events) == 1
        assert events[0]["type"] == "session.paused"
        assert events[0]["session_id"] == str(SESSION_ID)


# ---------------------------------------------------------------------------
# Unit: CodexCLIEngine - approve / reject
# ---------------------------------------------------------------------------


class TestApproveReject:
    """Tests for approve_action and reject_action."""

    @pytest.mark.asyncio
    async def test_approve_action(self) -> None:
        """approve_action marks a pending action as approved."""
        engine = CodexCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        engine._sessions[SESSION_ID].pending_actions["act-1"] = {"status": "pending"}
        await engine.approve_action(SESSION_ID, "act-1")
        assert engine._sessions[SESSION_ID].pending_actions["act-1"]["approved"] is True

    @pytest.mark.asyncio
    async def test_reject_action(self) -> None:
        """reject_action marks a pending action as rejected."""
        engine = CodexCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        engine._sessions[SESSION_ID].pending_actions["act-2"] = {"status": "pending"}
        await engine.reject_action(SESSION_ID, "act-2")
        assert engine._sessions[SESSION_ID].pending_actions["act-2"]["rejected"] is True


# ---------------------------------------------------------------------------
# Unit: CodexCLIEngine - get_diff
# ---------------------------------------------------------------------------


class TestGetDiff:
    """Tests for CodexCLIEngine.get_diff."""

    @pytest.mark.asyncio
    async def test_get_diff_returns_tracked_changes(self) -> None:
        """get_diff returns diffs tracked by DiffService."""
        diff_service = DiffService()
        diff_service.track_change(str(SESSION_ID), "src/main.py", "--- a\n+++ b\n+new line")
        engine = CodexCLIEngine(diff_service=diff_service)
        result = await engine.get_diff(SESSION_ID)
        assert isinstance(result, dict)
        assert "src/main.py" in result
        assert "+new line" in result["src/main.py"]

    @pytest.mark.asyncio
    async def test_get_diff_empty_when_no_changes(self) -> None:
        """get_diff returns empty dict when there are no tracked changes."""
        engine = CodexCLIEngine(diff_service=DiffService())
        result = await engine.get_diff(SESSION_ID)
        assert result == {}


# ---------------------------------------------------------------------------
# Unit: CodexCLIEngine - start_task
# ---------------------------------------------------------------------------


class TestStartTask:
    """Tests for CodexCLIEngine.start_task."""

    @pytest.mark.asyncio
    async def test_start_task_delegates_to_send_message(self) -> None:
        """start_task sends task instructions via send_message."""
        stream_lines = [
            json.dumps({"type": "message", "content": "Task done."}).encode() + b"\n",
        ]
        proc = _make_mock_process(returncode=None, stdout_lines=stream_lines)
        engine = CodexCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
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


# ---------------------------------------------------------------------------
# Unit: CodexCLIEngine - cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    """Tests for session cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_session_removes_state(self) -> None:
        """cleanup_session removes session state."""
        engine = CodexCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.cleanup_session(SESSION_ID)
        assert SESSION_ID not in engine._sessions

    @pytest.mark.asyncio
    async def test_cleanup_session_stops_process(self) -> None:
        """cleanup_session stops any running process."""
        proc = _make_mock_process(returncode=None)

        async def fake_wait():
            proc.returncode = 0

        proc.wait = AsyncMock(side_effect=fake_wait)

        engine = CodexCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            # Trigger a send to create a process
            stream_lines_iter = iter([b""])
            proc.stdout.readline = AsyncMock(side_effect=lambda: next(stream_lines_iter))
            await _collect_events(engine.send_message(SESSION_ID, "test"))
            await engine.cleanup_session(SESSION_ID)

        assert SESSION_ID not in engine._sessions
        proc.terminate.assert_called_once()


# ---------------------------------------------------------------------------
# Integration: Engine wiring in _build_engine
# ---------------------------------------------------------------------------


class TestEngineWiring:
    """Tests for _build_engine engine type routing."""

    @pytest.mark.asyncio
    async def test_build_engine_returns_codex_cli_engine(self) -> None:
        """_build_engine returns CodexCLIEngine for 'codex_cli'."""
        from codehive.api.routes.sessions import _build_engine

        engine = await _build_engine({"project_root": "/tmp"}, engine_type="codex_cli")
        assert isinstance(engine, CodexCLIEngine)

    @pytest.mark.asyncio
    async def test_build_engine_codex_still_works(self) -> None:
        """_build_engine still returns CodexEngine for 'codex' (no regression)."""
        from unittest.mock import patch as mock_patch

        from codehive.api.routes.sessions import _build_engine
        from codehive.engine.codex import CodexEngine

        with mock_patch.dict(
            "os.environ",
            {"CODEHIVE_OPENAI_API_KEY": "test-key"},
        ):
            engine = await _build_engine({"project_root": "/tmp"}, engine_type="codex")
            assert isinstance(engine, CodexEngine)

    @pytest.mark.asyncio
    async def test_build_engine_claude_code_still_works(self) -> None:
        """_build_engine still returns ClaudeCodeEngine for 'claude_code' (no regression)."""
        from codehive.api.routes.sessions import _build_engine
        from codehive.engine.claude_code_engine import ClaudeCodeEngine

        engine = await _build_engine({"project_root": "/tmp"}, engine_type="claude_code")
        assert isinstance(engine, ClaudeCodeEngine)

    @pytest.mark.asyncio
    async def test_build_engine_unknown_raises_400(self) -> None:
        """_build_engine raises HTTPException 400 for unknown engine type."""
        from fastapi import HTTPException

        from codehive.api.routes.sessions import _build_engine

        with pytest.raises(HTTPException) as exc_info:
            await _build_engine({}, engine_type="unknown_engine")
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Integration: Full pipeline (Process + Parser + Engine)
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """End-to-end: mocked JSONL through CodexCLIEngine.send_message."""

    @pytest.mark.asyncio
    async def test_full_pipeline_events(self) -> None:
        """Feed mocked JSONL and verify correct codehive events end-to-end."""
        stream_lines = [
            json.dumps({"type": "message", "content": "Let me help."}).encode() + b"\n",
            json.dumps(
                {"type": "command", "name": "read_file", "input": {"path": "foo.py"}}
            ).encode()
            + b"\n",
            json.dumps(
                {"type": "command_result", "name": "read_file", "output": "file contents"}
            ).encode()
            + b"\n",
            json.dumps({"type": "message", "content": "Done!"}).encode() + b"\n",
        ]
        proc = _make_mock_process(returncode=None, stdout_lines=stream_lines)
        engine = CodexCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.codex_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "Help me"))

        assert len(events) == 4
        assert events[0]["type"] == "message.created"
        assert events[0]["content"] == "Let me help."
        assert events[1]["type"] == "tool.call.started"
        assert events[1]["tool_name"] == "read_file"
        assert events[2]["type"] == "tool.call.finished"
        assert events[2]["tool_name"] == "read_file"
        assert events[3]["type"] == "message.created"
        assert events[3]["content"] == "Done!"

        # All events have session_id
        for evt in events:
            assert evt["session_id"] == str(SESSION_ID)
