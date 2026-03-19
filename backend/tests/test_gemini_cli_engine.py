"""Tests for GeminiCLIEngine, GeminiCLIProcess, and GeminiCLIParser.

All tests use mocked subprocess -- no real ``gemini`` CLI invocation.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codehive.engine.base import EngineAdapter
from codehive.engine.gemini_cli_engine import GeminiCLIEngine
from codehive.engine.gemini_cli_parser import GeminiCLIParser
from codehive.engine.gemini_cli_process import GeminiCLIProcess, GeminiProcessError
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
    """Create a mock asyncio.subprocess.Process."""
    proc = MagicMock()
    proc.returncode = returncode

    if stdout_lines is None:
        stdout_lines = []
    line_iter = iter(stdout_lines + [b""])
    proc.stdout = MagicMock()
    proc.stdout.readline = AsyncMock(side_effect=lambda: next(line_iter))

    proc.stderr = MagicMock()
    proc.stderr.read = AsyncMock(return_value=stderr_data)

    proc.wait = AsyncMock()

    return proc


async def _collect_events(aiter: Any) -> list[dict]:
    """Collect all events from an async iterator."""
    events: list[dict] = []
    async for event in aiter:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Unit: GeminiCLIParser
# ---------------------------------------------------------------------------


class TestGeminiCLIParser:
    """Unit tests for GeminiCLIParser.parse_line()."""

    @pytest.fixture
    def parser(self) -> GeminiCLIParser:
        return GeminiCLIParser()

    def test_parse_init_event(self, parser: GeminiCLIParser) -> None:
        """Parse init event into session.started with gemini_session_id and model."""
        line = json.dumps(
            {
                "type": "init",
                "timestamp": "2026-03-19T04:54:07.160Z",
                "session_id": "cc70e0b5-356e-45ee-ba9d-ab691ed0c31e",
                "model": "auto-gemini-3",
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "session.started"
        assert events[0]["gemini_session_id"] == "cc70e0b5-356e-45ee-ba9d-ab691ed0c31e"
        assert events[0]["model"] == "auto-gemini-3"
        assert events[0]["session_id"] == str(SESSION_ID)

    def test_parse_message_delta(self, parser: GeminiCLIParser) -> None:
        """Parse assistant message with delta=true into message.delta."""
        line = json.dumps(
            {
                "type": "message",
                "role": "assistant",
                "content": "Hello! I'm Gemini CLI,",
                "delta": True,
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.delta"
        assert events[0]["role"] == "assistant"
        assert events[0]["content"] == "Hello! I'm Gemini CLI,"
        assert events[0]["session_id"] == str(SESSION_ID)

    def test_parse_message_delta_empty_content(self, parser: GeminiCLIParser) -> None:
        """message with delta=true and empty content returns empty list."""
        line = json.dumps(
            {
                "type": "message",
                "role": "assistant",
                "content": "",
                "delta": True,
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert events == []

    def test_parse_message_created(self, parser: GeminiCLIParser) -> None:
        """Parse assistant message without delta into message.created."""
        line = json.dumps(
            {
                "type": "message",
                "role": "assistant",
                "content": "Complete response here.",
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.created"
        assert events[0]["role"] == "assistant"
        assert events[0]["content"] == "Complete response here."

    def test_parse_message_user_skip(self, parser: GeminiCLIParser) -> None:
        """Parse user message returns empty list (skip echo)."""
        line = json.dumps(
            {
                "type": "message",
                "role": "user",
                "content": "say hello",
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert events == []

    def test_parse_tool_use(self, parser: GeminiCLIParser) -> None:
        """Parse tool_use into tool.call.started with tool_name and tool_input from parameters."""
        line = json.dumps(
            {
                "type": "tool_use",
                "tool_name": "run_shell_command",
                "tool_id": "run_shell_command_123_0",
                "parameters": {"description": "List files", "command": "ls /tmp"},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "tool.call.started"
        assert events[0]["tool_name"] == "run_shell_command"
        assert events[0]["tool_input"] == {"description": "List files", "command": "ls /tmp"}
        assert events[0]["session_id"] == str(SESSION_ID)

    def test_parse_tool_result_success(self, parser: GeminiCLIParser) -> None:
        """Parse tool_result (status=success) into tool.call.finished with output."""
        line = json.dumps(
            {
                "type": "tool_result",
                "tool_id": "run_shell_command_123_0",
                "status": "success",
                "output": "file1.py\nfile2.py",
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "tool.call.finished"
        assert events[0]["result"] == "file1.py\nfile2.py"

    def test_parse_tool_result_success_no_output(self, parser: GeminiCLIParser) -> None:
        """Parse tool_result (status=success, no output field) -> empty result."""
        line = json.dumps(
            {
                "type": "tool_result",
                "tool_id": "some_tool_123",
                "status": "success",
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "tool.call.finished"
        assert events[0]["result"] == ""

    def test_parse_tool_result_error(self, parser: GeminiCLIParser) -> None:
        """Parse tool_result (status=error) into tool.call.finished with ERROR prefix."""
        line = json.dumps(
            {
                "type": "tool_result",
                "tool_id": "tool_456",
                "status": "error",
                "error": {"type": "invalid_tool_params", "message": "Missing required param"},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "tool.call.finished"
        assert events[0]["result"].startswith("ERROR: ")
        assert "Missing required param" in events[0]["result"]

    def test_parse_tool_result_write_file_emits_file_changed(self, parser: GeminiCLIParser) -> None:
        """tool_result for write_file emits tool.call.finished + file.changed."""
        # First register tool_use so parser knows the tool_name
        tool_use_line = json.dumps(
            {
                "type": "tool_use",
                "tool_name": "write_file",
                "tool_id": "write_file_789",
                "parameters": {"file_path": "src/main.py", "content": "print('hello')"},
            }
        )
        parser.parse_line(tool_use_line, SESSION_ID)

        # Now the result
        result_line = json.dumps(
            {
                "type": "tool_result",
                "tool_id": "write_file_789",
                "status": "success",
            }
        )
        events = parser.parse_line(result_line, SESSION_ID)
        assert len(events) == 2
        assert events[0]["type"] == "tool.call.finished"
        assert events[0]["tool_name"] == "write_file"
        assert events[1]["type"] == "file.changed"
        assert events[1]["path"] == "src/main.py"

    def test_parse_tool_result_edit_file_emits_file_changed(self, parser: GeminiCLIParser) -> None:
        """tool_result for edit_file emits tool.call.finished + file.changed."""
        tool_use_line = json.dumps(
            {
                "type": "tool_use",
                "tool_name": "edit_file",
                "tool_id": "edit_file_321",
                "parameters": {"file_path": "src/utils.py", "old_text": "a", "new_text": "b"},
            }
        )
        parser.parse_line(tool_use_line, SESSION_ID)

        result_line = json.dumps(
            {
                "type": "tool_result",
                "tool_id": "edit_file_321",
                "status": "success",
            }
        )
        events = parser.parse_line(result_line, SESSION_ID)
        assert len(events) == 2
        assert events[0]["type"] == "tool.call.finished"
        assert events[1]["type"] == "file.changed"
        assert events[1]["path"] == "src/utils.py"

    def test_parse_result_event(self, parser: GeminiCLIParser) -> None:
        """Parse result event into session.completed with stats and per-model usage."""
        # Set gemini_session_id via init first
        init_line = json.dumps(
            {
                "type": "init",
                "session_id": "gemini-sid-abc",
                "model": "auto-gemini-3",
            }
        )
        parser.parse_line(init_line, SESSION_ID)

        result_line = json.dumps(
            {
                "type": "result",
                "status": "success",
                "stats": {
                    "total_tokens": 11503,
                    "input_tokens": 11338,
                    "output_tokens": 57,
                    "cached": 0,
                    "duration_ms": 3375,
                    "tool_calls": 0,
                    "models": {"gemini-2.5-pro": {"input_tokens": 11338, "output_tokens": 57}},
                },
            }
        )
        events = parser.parse_line(result_line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "session.completed"
        assert events[0]["gemini_session_id"] == "gemini-sid-abc"
        assert events[0]["usage"]["total_tokens"] == 11503
        assert events[0]["usage"]["input_tokens"] == 11338
        assert events[0]["usage"]["output_tokens"] == 57
        assert events[0]["usage"]["duration_ms"] == 3375
        assert "gemini-2.5-pro" in events[0]["usage"]["models"]

    def test_malformed_json(self, parser: GeminiCLIParser) -> None:
        """Malformed JSON returns empty list, no crash."""
        events = parser.parse_line("this is not json {{{", SESSION_ID)
        assert events == []

    def test_empty_line(self, parser: GeminiCLIParser) -> None:
        """Empty lines return empty list."""
        assert parser.parse_line("", SESSION_ID) == []
        assert parser.parse_line("   \n  ", SESSION_ID) == []

    def test_non_dict_json(self, parser: GeminiCLIParser) -> None:
        """A JSON array (non-object) returns empty list."""
        events = parser.parse_line("[1, 2, 3]", SESSION_ID)
        assert events == []

    def test_all_events_include_type_and_session_id(self, parser: GeminiCLIParser) -> None:
        """Every event includes session_id and type keys."""
        lines = [
            json.dumps({"type": "init", "session_id": "sid-abc", "model": "m"}),
            json.dumps({"type": "message", "role": "assistant", "content": "hi", "delta": True}),
            json.dumps({"type": "message", "role": "assistant", "content": "hello"}),
            json.dumps(
                {
                    "type": "tool_use",
                    "tool_name": "bash",
                    "tool_id": "t1",
                    "parameters": {},
                }
            ),
            json.dumps({"type": "tool_result", "tool_id": "t1", "status": "success"}),
            json.dumps({"type": "result", "status": "success", "stats": {}}),
        ]
        for line in lines:
            for evt in parser.parse_line(line, SESSION_ID):
                assert "type" in evt, f"Missing 'type' in event from: {line}"
                assert "session_id" in evt, f"Missing 'session_id' in event from: {line}"
                assert evt["session_id"] == str(SESSION_ID)


# ---------------------------------------------------------------------------
# Unit: GeminiCLIProcess
# ---------------------------------------------------------------------------


class TestGeminiCLIProcess:
    """Unit tests for GeminiCLIProcess."""

    def test_build_command_basic(self) -> None:
        """_build_command returns correct command with default flags."""
        p = GeminiCLIProcess()
        cmd = p._build_command("hello world")
        assert cmd[0] == "gemini"
        assert "-p" in cmd
        assert "hello world" in cmd
        assert "--output-format" in cmd
        idx = cmd.index("--output-format")
        assert cmd[idx + 1] == "stream-json"
        assert "--yolo" in cmd

    def test_build_command_with_resume(self) -> None:
        """_build_command includes --resume <sessionId> as separate args."""
        p = GeminiCLIProcess()
        cmd = p._build_command("test", resume_session_id="abc-123")
        assert "--resume" in cmd
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "abc-123"

    def test_build_command_no_resume_when_none(self) -> None:
        """_build_command omits --resume when session_id is None."""
        p = GeminiCLIProcess()
        cmd = p._build_command("test")
        assert "--resume" not in cmd

    def test_build_command_with_extra_flags(self) -> None:
        """_build_command includes extra_flags."""
        p = GeminiCLIProcess(extra_flags=["--sandbox", "-m", "gemini-pro"])
        cmd = p._build_command("test")
        assert "--sandbox" in cmd
        assert "-m" in cmd
        assert "gemini-pro" in cmd

    @pytest.mark.asyncio
    async def test_run_yields_stdout_lines(self) -> None:
        """run() yields decoded stdout lines."""
        line_data = json.dumps({"type": "message", "role": "assistant", "content": "hi"})
        proc = _make_mock_process(
            returncode=0,
            stdout_lines=[f"{line_data}\n".encode()],
        )

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = GeminiCLIProcess()
            lines = []
            async for line in p.run("test"):
                lines.append(line)

            assert len(lines) == 1
            assert lines[0] == line_data

    @pytest.mark.asyncio
    async def test_run_raises_on_nonzero_exit(self) -> None:
        """run() raises GeminiProcessError on non-zero exit code."""
        proc = _make_mock_process(
            returncode=1,
            stdout_lines=[],
            stderr_data=b"Error occurred",
        )

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = GeminiCLIProcess()
            with pytest.raises(GeminiProcessError) as exc_info:
                async for _ in p.run("test"):
                    pass
            assert exc_info.value.exit_code == 1
            assert "Error occurred" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_skips_empty_lines(self) -> None:
        """run() does not yield empty lines."""
        proc = _make_mock_process(
            returncode=0,
            stdout_lines=[b"\n", b'{"type":"test"}\n', b"\n"],
        )

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = GeminiCLIProcess()
            lines = []
            async for line in p.run("test"):
                lines.append(line)
            assert len(lines) == 1

    @pytest.mark.asyncio
    async def test_run_sets_cwd_to_working_dir(self) -> None:
        """run() passes cwd=working_dir to subprocess."""
        proc = _make_mock_process(returncode=0, stdout_lines=[])

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = GeminiCLIProcess(working_dir="/home/user/project")
            async for _ in p.run("test"):
                pass

            _, kwargs = mock_exec.call_args
            assert kwargs.get("cwd") == "/home/user/project"

    @pytest.mark.asyncio
    async def test_run_no_cwd_when_no_working_dir(self) -> None:
        """run() does not pass cwd when working_dir is None."""
        proc = _make_mock_process(returncode=0, stdout_lines=[])

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = GeminiCLIProcess()
            async for _ in p.run("test"):
                pass

            _, kwargs = mock_exec.call_args
            assert "cwd" not in kwargs


# ---------------------------------------------------------------------------
# Unit: GeminiCLIEngine - Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Verify GeminiCLIEngine satisfies the EngineAdapter protocol."""

    def test_isinstance_check(self) -> None:
        """GeminiCLIEngine is recognised as an EngineAdapter."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        assert isinstance(engine, EngineAdapter)

    def test_all_protocol_methods_exist(self) -> None:
        """All 8 protocol methods exist and are callable."""
        engine = GeminiCLIEngine(diff_service=DiffService())
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
# Unit: GeminiCLIEngine - create_session
# ---------------------------------------------------------------------------


class TestCreateSession:
    """Tests for GeminiCLIEngine.create_session."""

    @pytest.mark.asyncio
    async def test_create_session_initializes_state(self) -> None:
        """create_session initializes session state."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        assert SESSION_ID in engine._sessions
        assert engine._sessions[SESSION_ID].paused is False
        assert engine._sessions[SESSION_ID].gemini_session_id is None

    @pytest.mark.asyncio
    async def test_create_session_duplicate_replaces(self) -> None:
        """Calling create_session twice replaces the old session state."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        state1 = engine._sessions[SESSION_ID]
        await engine.create_session(SESSION_ID)
        state2 = engine._sessions[SESSION_ID]
        assert state1 is not state2


# ---------------------------------------------------------------------------
# Unit: GeminiCLIEngine - send_message
# ---------------------------------------------------------------------------


class TestSendMessage:
    """Tests for GeminiCLIEngine.send_message."""

    @pytest.mark.asyncio
    async def test_send_message_yields_events(self) -> None:
        """send_message yields parsed codehive events from subprocess stdout."""
        stream_lines = [
            json.dumps(
                {
                    "type": "init",
                    "session_id": "gemini-sid-1",
                    "model": "auto-gemini-3",
                }
            ).encode()
            + b"\n",
            json.dumps(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": "Hello!",
                    "delta": True,
                }
            ).encode()
            + b"\n",
            json.dumps(
                {
                    "type": "tool_use",
                    "tool_name": "run_shell_command",
                    "tool_id": "t1",
                    "parameters": {"command": "ls"},
                }
            ).encode()
            + b"\n",
            json.dumps(
                {
                    "type": "tool_result",
                    "tool_id": "t1",
                    "status": "success",
                    "output": "file1.py",
                }
            ).encode()
            + b"\n",
        ]
        proc = _make_mock_process(returncode=0, stdout_lines=stream_lines)
        engine = GeminiCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            events = await _collect_events(engine.send_message(SESSION_ID, "Hello"))

        assert len(events) == 4
        assert events[0]["type"] == "session.started"
        assert events[1]["type"] == "message.delta"
        assert events[1]["content"] == "Hello!"
        assert events[2]["type"] == "tool.call.started"
        assert events[3]["type"] == "tool.call.finished"

    @pytest.mark.asyncio
    async def test_send_message_captures_session_id_from_init(self) -> None:
        """send_message captures gemini_session_id from init event."""
        stream_lines = [
            json.dumps(
                {
                    "type": "init",
                    "session_id": "gemini-sid-abc",
                    "model": "auto-gemini-3",
                }
            ).encode()
            + b"\n",
        ]
        proc = _make_mock_process(returncode=0, stdout_lines=stream_lines)
        engine = GeminiCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            await _collect_events(engine.send_message(SESSION_ID, "Hello"))

        assert engine._sessions[SESSION_ID].gemini_session_id == "gemini-sid-abc"

    @pytest.mark.asyncio
    async def test_send_message_uses_resume_on_second_call(self) -> None:
        """send_message uses --resume <sessionId> on second call."""
        first_lines = [
            json.dumps(
                {
                    "type": "init",
                    "session_id": "gemini-sid-xyz",
                    "model": "auto-gemini-3",
                }
            ).encode()
            + b"\n",
        ]
        second_lines = [
            json.dumps(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": "Resumed!",
                }
            ).encode()
            + b"\n",
        ]

        call_count = 0
        procs = [
            _make_mock_process(returncode=0, stdout_lines=first_lines),
            _make_mock_process(returncode=0, stdout_lines=second_lines),
        ]

        async def mock_exec(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            p = procs[call_count]
            call_count += 1
            return p

        engine = GeminiCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=mock_exec),
        ) as mock_create:
            await engine.create_session(SESSION_ID)
            await _collect_events(engine.send_message(SESSION_ID, "First"))
            await _collect_events(engine.send_message(SESSION_ID, "Second"))

            # Verify second call includes --resume gemini-sid-xyz
            second_call_args = mock_create.call_args_list[1][0]
            assert "--resume" in second_call_args
            resume_idx = list(second_call_args).index("--resume")
            assert second_call_args[resume_idx + 1] == "gemini-sid-xyz"

    @pytest.mark.asyncio
    async def test_send_message_nonexistent_session_raises(self) -> None:
        """send_message on a non-existent session raises KeyError."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        with pytest.raises(KeyError, match="not found"):
            await _collect_events(engine.send_message(uuid.uuid4(), "hello"))

    @pytest.mark.asyncio
    async def test_send_message_crash_with_retry(self) -> None:
        """If process crashes, engine retries with --resume."""
        # First call succeeds, provides init event with session ID
        first_lines = [
            json.dumps(
                {
                    "type": "init",
                    "session_id": "retry-sid",
                    "model": "auto-gemini-3",
                }
            ).encode()
            + b"\n",
        ]
        first_proc = _make_mock_process(returncode=0, stdout_lines=first_lines)

        # Second call crashes
        crash_proc = _make_mock_process(returncode=1, stderr_data=b"Crash!")
        # Retry succeeds
        retry_lines = [
            json.dumps(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": "Recovered!",
                }
            ).encode()
            + b"\n",
        ]
        retry_proc = _make_mock_process(returncode=0, stdout_lines=retry_lines)

        call_count = 0
        procs = [first_proc, crash_proc, retry_proc]

        async def mock_exec(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            p = procs[call_count]
            call_count += 1
            return p

        engine = GeminiCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=mock_exec),
        ):
            await engine.create_session(SESSION_ID)
            # First call succeeds, sets session ID
            await _collect_events(engine.send_message(SESSION_ID, "First"))
            # Second call crashes, engine retries
            events = await _collect_events(engine.send_message(SESSION_ID, "Crash me"))

        # Should get the recovery message from retry
        assert any(e["type"] == "message.created" and e["content"] == "Recovered!" for e in events)

    @pytest.mark.asyncio
    async def test_send_message_all_retries_exhausted(self) -> None:
        """When all retries are exhausted, yields session.failed."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        # Pre-set a gemini session ID so retries are attempted
        engine._sessions[SESSION_ID].gemini_session_id = "existing-sid"

        # All processes crash
        crash_procs = [_make_mock_process(returncode=1, stderr_data=b"crash") for _ in range(5)]
        call_count = 0

        async def mock_exec(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            p = crash_procs[min(call_count, len(crash_procs) - 1)]
            call_count += 1
            return p

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=mock_exec),
        ):
            events = await _collect_events(engine.send_message(SESSION_ID, "test"))

        # Should end with session.failed
        assert any(e["type"] == "session.failed" for e in events)

    @pytest.mark.asyncio
    async def test_send_message_crash_no_session_id(self) -> None:
        """Crash with no gemini session ID yields session.failed immediately."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        # No gemini_session_id set

        crash_proc = _make_mock_process(returncode=1, stderr_data=b"crash")

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=crash_proc),
        ):
            events = await _collect_events(engine.send_message(SESSION_ID, "test"))

        assert len(events) == 1
        assert events[0]["type"] == "session.failed"
        assert "no gemini session ID" in events[0]["error"]


# ---------------------------------------------------------------------------
# Unit: GeminiCLIEngine - pause / resume
# ---------------------------------------------------------------------------


class TestPauseResume:
    """Tests for pause and resume."""

    @pytest.mark.asyncio
    async def test_pause_marks_session_paused(self) -> None:
        """pause() sets the paused flag."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.pause(SESSION_ID)
        assert engine._sessions[SESSION_ID].paused is True

    @pytest.mark.asyncio
    async def test_resume_clears_pause(self) -> None:
        """resume() clears the paused flag."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.pause(SESSION_ID)
        await engine.resume(SESSION_ID)
        assert engine._sessions[SESSION_ID].paused is False

    @pytest.mark.asyncio
    async def test_send_message_while_paused_yields_paused_event(self) -> None:
        """send_message while paused yields session.paused and stops."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.pause(SESSION_ID)
        events = await _collect_events(engine.send_message(SESSION_ID, "hello"))

        assert len(events) == 1
        assert events[0]["type"] == "session.paused"
        assert events[0]["session_id"] == str(SESSION_ID)


# ---------------------------------------------------------------------------
# Unit: GeminiCLIEngine - approve / reject
# ---------------------------------------------------------------------------


class TestApproveReject:
    """Tests for approve_action and reject_action."""

    @pytest.mark.asyncio
    async def test_approve_action(self) -> None:
        """approve_action marks a pending action as approved."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        engine._sessions[SESSION_ID].pending_actions["act-1"] = {"status": "pending"}
        await engine.approve_action(SESSION_ID, "act-1")
        assert engine._sessions[SESSION_ID].pending_actions["act-1"]["approved"] is True

    @pytest.mark.asyncio
    async def test_reject_action(self) -> None:
        """reject_action marks a pending action as rejected."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        engine._sessions[SESSION_ID].pending_actions["act-2"] = {"status": "pending"}
        await engine.reject_action(SESSION_ID, "act-2")
        assert engine._sessions[SESSION_ID].pending_actions["act-2"]["rejected"] is True


# ---------------------------------------------------------------------------
# Unit: GeminiCLIEngine - get_diff
# ---------------------------------------------------------------------------


class TestGetDiff:
    """Tests for GeminiCLIEngine.get_diff."""

    @pytest.mark.asyncio
    async def test_get_diff_returns_tracked_changes(self) -> None:
        """get_diff returns diffs tracked by DiffService."""
        diff_service = DiffService()
        diff_service.track_change(str(SESSION_ID), "src/main.py", "--- a\n+++ b\n+new line")
        engine = GeminiCLIEngine(diff_service=diff_service)
        result = await engine.get_diff(SESSION_ID)
        assert isinstance(result, dict)
        assert "src/main.py" in result
        assert "+new line" in result["src/main.py"]

    @pytest.mark.asyncio
    async def test_get_diff_empty_when_no_changes(self) -> None:
        """get_diff returns empty dict when there are no tracked changes."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        result = await engine.get_diff(SESSION_ID)
        assert result == {}


# ---------------------------------------------------------------------------
# Unit: GeminiCLIEngine - start_task
# ---------------------------------------------------------------------------


class TestStartTask:
    """Tests for GeminiCLIEngine.start_task."""

    @pytest.mark.asyncio
    async def test_start_task_delegates_to_send_message(self) -> None:
        """start_task sends task instructions via send_message."""
        stream_lines = [
            json.dumps(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": "Task done.",
                }
            ).encode()
            + b"\n",
        ]
        proc = _make_mock_process(returncode=0, stdout_lines=stream_lines)
        engine = GeminiCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.gemini_cli_process.asyncio.create_subprocess_exec",
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
# Unit: GeminiCLIEngine - cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    """Tests for session cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_session_removes_state(self) -> None:
        """cleanup_session removes session state."""
        engine = GeminiCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.cleanup_session(SESSION_ID)
        assert SESSION_ID not in engine._sessions


# ---------------------------------------------------------------------------
# Integration: Engine wiring in _build_engine
# ---------------------------------------------------------------------------


class TestEngineWiring:
    """Tests for _build_engine gemini_cli engine type routing."""

    @pytest.mark.asyncio
    async def test_build_engine_returns_gemini_cli_engine(self) -> None:
        """_build_engine returns GeminiCLIEngine for 'gemini_cli'."""
        from codehive.api.routes.sessions import _build_engine

        engine = await _build_engine({"project_root": "/tmp"}, engine_type="gemini_cli")
        assert isinstance(engine, GeminiCLIEngine)


# ---------------------------------------------------------------------------
# Integration: Provider detection
# ---------------------------------------------------------------------------


class TestProviderDetection:
    """Tests for gemini provider in /api/providers endpoint."""

    @pytest.mark.asyncio
    async def test_gemini_available_when_cli_found(self, monkeypatch, tmp_path) -> None:
        """Gemini is available when gemini CLI is on PATH."""
        for key in list(__import__("os").environ):
            if key.startswith("CODEHIVE_"):
                monkeypatch.delenv(key, raising=False)
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ZAI_API_KEY", "OPENAI_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.chdir(tmp_path)

        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.side_effect = lambda name: (
                "/usr/bin/gemini" if name == "gemini" else None
            )
            result = await list_providers()

        gemini = next(p for p in result if p.name == "gemini")
        assert gemini.available is True
        assert gemini.type == "cli"
        assert "CLI found" in gemini.reason

    @pytest.mark.asyncio
    async def test_gemini_unavailable_when_cli_missing(self, monkeypatch, tmp_path) -> None:
        """Gemini is unavailable when gemini CLI is not on PATH."""
        for key in list(__import__("os").environ):
            if key.startswith("CODEHIVE_"):
                monkeypatch.delenv(key, raising=False)
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ZAI_API_KEY", "OPENAI_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.chdir(tmp_path)

        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        gemini = next(p for p in result if p.name == "gemini")
        assert gemini.available is False
        assert gemini.reason == "CLI not found"

    @pytest.mark.asyncio
    async def test_provider_count_is_six(self, monkeypatch, tmp_path) -> None:
        """Provider list has 6 entries: claude, codex, openai, zai, copilot, gemini."""
        for key in list(__import__("os").environ):
            if key.startswith("CODEHIVE_"):
                monkeypatch.delenv(key, raising=False)
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ZAI_API_KEY", "OPENAI_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.chdir(tmp_path)

        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        assert len(result) == 6
        names = {p.name for p in result}
        assert names == {"claude", "codex", "openai", "zai", "copilot", "gemini"}
