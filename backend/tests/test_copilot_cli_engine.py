"""Tests for CopilotCLIEngine, CopilotCLIProcess, and CopilotCLIParser.

All tests use mocked subprocess -- no real ``copilot`` CLI invocation.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codehive.engine.base import EngineAdapter
from codehive.engine.copilot_cli_engine import CopilotCLIEngine
from codehive.engine.copilot_cli_parser import CopilotCLIParser
from codehive.engine.copilot_cli_process import CopilotCLIProcess, CopilotProcessError
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
# Unit: CopilotCLIParser
# ---------------------------------------------------------------------------


class TestCopilotCLIParser:
    """Unit tests for CopilotCLIParser.parse_line()."""

    @pytest.fixture
    def parser(self) -> CopilotCLIParser:
        return CopilotCLIParser()

    def test_parse_message_delta(self, parser: CopilotCLIParser) -> None:
        """Parse assistant.message_delta into message.delta."""
        line = json.dumps(
            {
                "type": "assistant.message_delta",
                "data": {"messageId": "abc", "deltaContent": "hello"},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.delta"
        assert events[0]["role"] == "assistant"
        assert events[0]["content"] == "hello"
        assert events[0]["session_id"] == str(SESSION_ID)

    def test_parse_assistant_message(self, parser: CopilotCLIParser) -> None:
        """Parse assistant.message into message.created."""
        line = json.dumps(
            {
                "type": "assistant.message",
                "data": {"content": "Hello from Copilot!"},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.created"
        assert events[0]["role"] == "assistant"
        assert events[0]["content"] == "Hello from Copilot!"

    def test_parse_assistant_message_with_tool_requests(self, parser: CopilotCLIParser) -> None:
        """Parse assistant.message with toolRequests still returns message.created."""
        line = json.dumps(
            {
                "type": "assistant.message",
                "data": {
                    "content": "Let me check.",
                    "toolRequests": [
                        {"toolCallId": "tc1", "name": "bash", "arguments": {"command": "ls"}},
                    ],
                },
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.created"
        assert events[0]["content"] == "Let me check."

    def test_parse_tool_execution_start(self, parser: CopilotCLIParser) -> None:
        """Parse tool.execution_start into tool.call.started."""
        line = json.dumps(
            {
                "type": "tool.execution_start",
                "data": {
                    "toolCallId": "x",
                    "toolName": "bash",
                    "arguments": {"command": "ls -la"},
                },
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "tool.call.started"
        assert events[0]["tool_name"] == "bash"
        assert events[0]["tool_input"] == {"command": "ls -la"}

    def test_parse_tool_execution_complete_success(self, parser: CopilotCLIParser) -> None:
        """Parse tool.execution_complete (success) into tool.call.finished."""
        line = json.dumps(
            {
                "type": "tool.execution_complete",
                "data": {
                    "toolCallId": "x",
                    "toolName": "bash",
                    "success": True,
                    "result": {"content": "file1.py\nfile2.py"},
                },
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "tool.call.finished"
        assert events[0]["tool_name"] == "bash"
        assert events[0]["result"] == "file1.py\nfile2.py"

    def test_parse_tool_execution_complete_failure(self, parser: CopilotCLIParser) -> None:
        """Parse tool.execution_complete (failure) includes ERROR prefix."""
        line = json.dumps(
            {
                "type": "tool.execution_complete",
                "data": {
                    "toolCallId": "x",
                    "toolName": "bash",
                    "success": False,
                    "result": {"content": "command not found"},
                },
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "tool.call.finished"
        assert "ERROR" in events[0]["result"]
        assert "command not found" in events[0]["result"]

    def test_parse_tool_execution_complete_file_edit(self, parser: CopilotCLIParser) -> None:
        """Tool execution_complete for 'write' tool emits tool.call.finished + file.changed."""
        line = json.dumps(
            {
                "type": "tool.execution_complete",
                "data": {
                    "toolCallId": "x",
                    "toolName": "write",
                    "success": True,
                    "result": {"content": "File written"},
                    "arguments": {"path": "src/main.py"},
                },
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 2
        assert events[0]["type"] == "tool.call.finished"
        assert events[1]["type"] == "file.changed"
        assert events[1]["path"] == "src/main.py"

    def test_parse_session_tools_updated(self, parser: CopilotCLIParser) -> None:
        """Parse session.tools_updated into session.started with model."""
        line = json.dumps(
            {
                "type": "session.tools_updated",
                "data": {"model": "gpt-4o"},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "session.started"
        assert events[0]["model"] == "gpt-4o"

    def test_parse_result_event(self, parser: CopilotCLIParser) -> None:
        """Parse result event into session.completed with sessionId and usage."""
        line = json.dumps(
            {
                "type": "result",
                "sessionId": "abc-123",
                "exitCode": 0,
                "usage": {"inputTokens": 100, "outputTokens": 50},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "session.completed"
        assert events[0]["copilot_session_id"] == "abc-123"
        assert events[0]["usage"] == {"inputTokens": 100, "outputTokens": 50}

    def test_skip_ephemeral_events(self, parser: CopilotCLIParser) -> None:
        """Ephemeral events return empty list."""
        ephemeral_types = [
            "session.mcp_servers_loaded",
            "session.mcp_server_status_changed",
            "assistant.reasoning_delta",
            "assistant.reasoning",
            "assistant.turn_start",
            "assistant.turn_end",
            "session.background_tasks_changed",
        ]
        for event_type in ephemeral_types:
            line = json.dumps({"type": event_type, "data": {}})
            events = parser.parse_line(line, SESSION_ID)
            assert events == [], f"Expected empty for {event_type}"

    def test_skip_user_message(self, parser: CopilotCLIParser) -> None:
        """user.message events return empty list."""
        line = json.dumps({"type": "user.message", "data": {"content": "hello"}})
        events = parser.parse_line(line, SESSION_ID)
        assert events == []

    def test_malformed_json(self, parser: CopilotCLIParser) -> None:
        """Malformed JSON returns empty list, no crash."""
        events = parser.parse_line("this is not json {{{", SESSION_ID)
        assert events == []

    def test_empty_line(self, parser: CopilotCLIParser) -> None:
        """Empty lines return empty list."""
        assert parser.parse_line("", SESSION_ID) == []
        assert parser.parse_line("   \n  ", SESSION_ID) == []

    def test_non_dict_json(self, parser: CopilotCLIParser) -> None:
        """A JSON array (non-object) returns empty list."""
        events = parser.parse_line("[1, 2, 3]", SESSION_ID)
        assert events == []

    def test_all_events_include_session_id(self, parser: CopilotCLIParser) -> None:
        """Every event includes session_id and type keys."""
        lines = [
            json.dumps({"type": "assistant.message_delta", "data": {"deltaContent": "hi"}}),
            json.dumps({"type": "assistant.message", "data": {"content": "hello"}}),
            json.dumps(
                {
                    "type": "tool.execution_start",
                    "data": {"toolCallId": "x", "toolName": "bash", "arguments": {}},
                }
            ),
            json.dumps(
                {
                    "type": "tool.execution_complete",
                    "data": {"toolCallId": "x", "toolName": "bash", "success": True, "result": {}},
                }
            ),
            json.dumps({"type": "session.tools_updated", "data": {"model": "gpt-4o"}}),
            json.dumps({"type": "result", "sessionId": "sid", "usage": {}}),
        ]
        for line in lines:
            for evt in parser.parse_line(line, SESSION_ID):
                assert "type" in evt, f"Missing 'type' in event from: {line}"
                assert "session_id" in evt, f"Missing 'session_id' in event from: {line}"
                assert evt["session_id"] == str(SESSION_ID)

    def test_parse_message_delta_empty_content(self, parser: CopilotCLIParser) -> None:
        """message_delta with empty deltaContent returns empty list."""
        line = json.dumps(
            {
                "type": "assistant.message_delta",
                "data": {"deltaContent": ""},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert events == []

    def test_parse_assistant_message_empty_content(self, parser: CopilotCLIParser) -> None:
        """assistant.message with empty content returns empty list."""
        line = json.dumps(
            {
                "type": "assistant.message",
                "data": {"content": ""},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert events == []


# ---------------------------------------------------------------------------
# Unit: CopilotCLIProcess
# ---------------------------------------------------------------------------


class TestCopilotCLIProcess:
    """Unit tests for CopilotCLIProcess."""

    def test_build_command_basic(self) -> None:
        """_build_command returns correct command with default flags."""
        p = CopilotCLIProcess()
        cmd = p._build_command("hello world")
        assert cmd[0] == "copilot"
        assert "-p" in cmd
        assert "hello world" in cmd
        assert "--output-format" in cmd
        idx = cmd.index("--output-format")
        assert cmd[idx + 1] == "json"
        assert "--allow-all-tools" in cmd
        assert "--autopilot" in cmd
        assert "--no-auto-update" in cmd

    def test_build_command_with_resume(self) -> None:
        """_build_command includes --resume=<sessionId>."""
        p = CopilotCLIProcess()
        cmd = p._build_command("test", resume_session_id="abc-123")
        assert "--resume=abc-123" in cmd

    def test_build_command_no_resume_when_none(self) -> None:
        """_build_command omits --resume when session_id is None."""
        p = CopilotCLIProcess()
        cmd = p._build_command("test")
        assert not any(c.startswith("--resume") for c in cmd)

    def test_build_command_with_working_dir(self) -> None:
        """_build_command includes --add-dir <dir>."""
        p = CopilotCLIProcess(working_dir="/home/user/project")
        cmd = p._build_command("test")
        idx = cmd.index("--add-dir")
        assert cmd[idx + 1] == "/home/user/project"

    def test_build_command_no_add_dir_when_none(self) -> None:
        """_build_command omits --add-dir when working_dir is None."""
        p = CopilotCLIProcess()
        cmd = p._build_command("test")
        assert "--add-dir" not in cmd

    def test_build_command_with_extra_flags(self) -> None:
        """_build_command includes extra_flags."""
        p = CopilotCLIProcess(extra_flags=["--debug", "--timeout=60"])
        cmd = p._build_command("test")
        assert "--debug" in cmd
        assert "--timeout=60" in cmd

    @pytest.mark.asyncio
    async def test_run_yields_stdout_lines(self) -> None:
        """run() yields decoded stdout lines."""
        line_data = json.dumps({"type": "assistant.message", "data": {"content": "hi"}})
        proc = _make_mock_process(
            returncode=0,
            stdout_lines=[f"{line_data}\n".encode()],
        )

        with patch(
            "codehive.engine.copilot_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = CopilotCLIProcess()
            lines = []
            async for line in p.run("test"):
                lines.append(line)

            assert len(lines) == 1
            assert lines[0] == line_data

    @pytest.mark.asyncio
    async def test_run_raises_on_nonzero_exit(self) -> None:
        """run() raises CopilotProcessError on non-zero exit code."""
        proc = _make_mock_process(
            returncode=1,
            stdout_lines=[],
            stderr_data=b"Error occurred",
        )

        with patch(
            "codehive.engine.copilot_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = CopilotCLIProcess()
            with pytest.raises(CopilotProcessError) as exc_info:
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
            "codehive.engine.copilot_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = CopilotCLIProcess()
            lines = []
            async for line in p.run("test"):
                lines.append(line)
            assert len(lines) == 1


# ---------------------------------------------------------------------------
# Unit: CopilotCLIEngine - Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Verify CopilotCLIEngine satisfies the EngineAdapter protocol."""

    def test_isinstance_check(self) -> None:
        """CopilotCLIEngine is recognised as an EngineAdapter."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        assert isinstance(engine, EngineAdapter)

    def test_all_protocol_methods_exist(self) -> None:
        """All 8 protocol methods exist and are callable."""
        engine = CopilotCLIEngine(diff_service=DiffService())
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
# Unit: CopilotCLIEngine - create_session
# ---------------------------------------------------------------------------


class TestCreateSession:
    """Tests for CopilotCLIEngine.create_session."""

    @pytest.mark.asyncio
    async def test_create_session_initializes_state(self) -> None:
        """create_session initializes session state."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        assert SESSION_ID in engine._sessions
        assert engine._sessions[SESSION_ID].paused is False
        assert engine._sessions[SESSION_ID].copilot_session_id is None

    @pytest.mark.asyncio
    async def test_create_session_duplicate_replaces(self) -> None:
        """Calling create_session twice replaces the old session state."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        state1 = engine._sessions[SESSION_ID]
        await engine.create_session(SESSION_ID)
        state2 = engine._sessions[SESSION_ID]
        assert state1 is not state2


# ---------------------------------------------------------------------------
# Unit: CopilotCLIEngine - send_message
# ---------------------------------------------------------------------------


class TestSendMessage:
    """Tests for CopilotCLIEngine.send_message."""

    @pytest.mark.asyncio
    async def test_send_message_yields_events(self) -> None:
        """send_message yields parsed codehive events from subprocess stdout."""
        stream_lines = [
            json.dumps(
                {
                    "type": "assistant.message",
                    "data": {"content": "Hello!"},
                }
            ).encode()
            + b"\n",
            json.dumps(
                {
                    "type": "tool.execution_start",
                    "data": {"toolCallId": "x", "toolName": "bash", "arguments": {"command": "ls"}},
                }
            ).encode()
            + b"\n",
            json.dumps(
                {
                    "type": "tool.execution_complete",
                    "data": {
                        "toolCallId": "x",
                        "toolName": "bash",
                        "success": True,
                        "result": {"content": "file1.py"},
                    },
                }
            ).encode()
            + b"\n",
        ]
        proc = _make_mock_process(returncode=0, stdout_lines=stream_lines)
        engine = CopilotCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.copilot_cli_process.asyncio.create_subprocess_exec",
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
    async def test_send_message_captures_session_id_from_result(self) -> None:
        """send_message captures copilot_session_id from result event."""
        stream_lines = [
            json.dumps(
                {
                    "type": "result",
                    "sessionId": "copilot-sid-abc",
                    "exitCode": 0,
                    "usage": {},
                }
            ).encode()
            + b"\n",
        ]
        proc = _make_mock_process(returncode=0, stdout_lines=stream_lines)
        engine = CopilotCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.copilot_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await engine.create_session(SESSION_ID)
            await _collect_events(engine.send_message(SESSION_ID, "Hello"))

        assert engine._sessions[SESSION_ID].copilot_session_id == "copilot-sid-abc"

    @pytest.mark.asyncio
    async def test_send_message_uses_resume_on_second_call(self) -> None:
        """send_message uses --resume=<sessionId> on second call."""
        # First call: result event sets the session ID
        first_lines = [
            json.dumps(
                {
                    "type": "result",
                    "sessionId": "copilot-sid-xyz",
                    "exitCode": 0,
                    "usage": {},
                }
            ).encode()
            + b"\n",
        ]
        # Second call: just a message
        second_lines = [
            json.dumps(
                {
                    "type": "assistant.message",
                    "data": {"content": "Resumed!"},
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

        engine = CopilotCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.copilot_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=mock_exec),
        ) as mock_create:
            await engine.create_session(SESSION_ID)
            await _collect_events(engine.send_message(SESSION_ID, "First"))
            await _collect_events(engine.send_message(SESSION_ID, "Second"))

            # Verify second call includes --resume=copilot-sid-xyz
            second_call_args = mock_create.call_args_list[1][0]
            assert "--resume=copilot-sid-xyz" in second_call_args

    @pytest.mark.asyncio
    async def test_send_message_nonexistent_session_raises(self) -> None:
        """send_message on a non-existent session raises KeyError."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        with pytest.raises(KeyError, match="not found"):
            await _collect_events(engine.send_message(uuid.uuid4(), "hello"))

    @pytest.mark.asyncio
    async def test_send_message_crash_with_retry(self) -> None:
        """If process crashes, engine retries with --resume."""
        # First call crashes but yields a result event first
        first_lines = [
            json.dumps(
                {
                    "type": "result",
                    "sessionId": "retry-sid",
                    "exitCode": 0,
                    "usage": {},
                }
            ).encode()
            + b"\n",
        ]
        # Set up the first process to return lines then crash
        first_proc = _make_mock_process(returncode=0, stdout_lines=first_lines)

        # The actual crash on the second call
        crash_proc = _make_mock_process(returncode=1, stderr_data=b"Crash!")
        # The retry succeeds
        retry_lines = [
            json.dumps(
                {
                    "type": "assistant.message",
                    "data": {"content": "Recovered!"},
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

        engine = CopilotCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.copilot_cli_process.asyncio.create_subprocess_exec",
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
        engine = CopilotCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        # Pre-set a copilot session ID so retries are attempted
        engine._sessions[SESSION_ID].copilot_session_id = "existing-sid"

        # All processes crash
        crash_procs = [
            _make_mock_process(returncode=1, stderr_data=b"crash")
            for _ in range(5)  # initial + MAX_RETRIES
        ]
        call_count = 0

        async def mock_exec(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            p = crash_procs[min(call_count, len(crash_procs) - 1)]
            call_count += 1
            return p

        with patch(
            "codehive.engine.copilot_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=mock_exec),
        ):
            events = await _collect_events(engine.send_message(SESSION_ID, "test"))

        # Should end with session.failed
        assert any(e["type"] == "session.failed" for e in events)

    @pytest.mark.asyncio
    async def test_send_message_crash_no_session_id(self) -> None:
        """Crash with no copilot session ID yields session.failed immediately."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        # No copilot_session_id set

        crash_proc = _make_mock_process(returncode=1, stderr_data=b"crash")

        with patch(
            "codehive.engine.copilot_cli_process.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=crash_proc),
        ):
            events = await _collect_events(engine.send_message(SESSION_ID, "test"))

        assert len(events) == 1
        assert events[0]["type"] == "session.failed"
        assert "no copilot session ID" in events[0]["error"]


# ---------------------------------------------------------------------------
# Unit: CopilotCLIEngine - pause / resume
# ---------------------------------------------------------------------------


class TestPauseResume:
    """Tests for pause and resume."""

    @pytest.mark.asyncio
    async def test_pause_marks_session_paused(self) -> None:
        """pause() sets the paused flag."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.pause(SESSION_ID)
        assert engine._sessions[SESSION_ID].paused is True

    @pytest.mark.asyncio
    async def test_resume_clears_pause(self) -> None:
        """resume() clears the paused flag."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.pause(SESSION_ID)
        await engine.resume(SESSION_ID)
        assert engine._sessions[SESSION_ID].paused is False

    @pytest.mark.asyncio
    async def test_send_message_while_paused_yields_paused_event(self) -> None:
        """send_message while paused yields session.paused and stops."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.pause(SESSION_ID)
        events = await _collect_events(engine.send_message(SESSION_ID, "hello"))

        assert len(events) == 1
        assert events[0]["type"] == "session.paused"
        assert events[0]["session_id"] == str(SESSION_ID)


# ---------------------------------------------------------------------------
# Unit: CopilotCLIEngine - approve / reject
# ---------------------------------------------------------------------------


class TestApproveReject:
    """Tests for approve_action and reject_action."""

    @pytest.mark.asyncio
    async def test_approve_action(self) -> None:
        """approve_action marks a pending action as approved."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        engine._sessions[SESSION_ID].pending_actions["act-1"] = {"status": "pending"}
        await engine.approve_action(SESSION_ID, "act-1")
        assert engine._sessions[SESSION_ID].pending_actions["act-1"]["approved"] is True

    @pytest.mark.asyncio
    async def test_reject_action(self) -> None:
        """reject_action marks a pending action as rejected."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        engine._sessions[SESSION_ID].pending_actions["act-2"] = {"status": "pending"}
        await engine.reject_action(SESSION_ID, "act-2")
        assert engine._sessions[SESSION_ID].pending_actions["act-2"]["rejected"] is True


# ---------------------------------------------------------------------------
# Unit: CopilotCLIEngine - get_diff
# ---------------------------------------------------------------------------


class TestGetDiff:
    """Tests for CopilotCLIEngine.get_diff."""

    @pytest.mark.asyncio
    async def test_get_diff_returns_tracked_changes(self) -> None:
        """get_diff returns diffs tracked by DiffService."""
        diff_service = DiffService()
        diff_service.track_change(str(SESSION_ID), "src/main.py", "--- a\n+++ b\n+new line")
        engine = CopilotCLIEngine(diff_service=diff_service)
        result = await engine.get_diff(SESSION_ID)
        assert isinstance(result, dict)
        assert "src/main.py" in result
        assert "+new line" in result["src/main.py"]

    @pytest.mark.asyncio
    async def test_get_diff_empty_when_no_changes(self) -> None:
        """get_diff returns empty dict when there are no tracked changes."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        result = await engine.get_diff(SESSION_ID)
        assert result == {}


# ---------------------------------------------------------------------------
# Unit: CopilotCLIEngine - start_task
# ---------------------------------------------------------------------------


class TestStartTask:
    """Tests for CopilotCLIEngine.start_task."""

    @pytest.mark.asyncio
    async def test_start_task_delegates_to_send_message(self) -> None:
        """start_task sends task instructions via send_message."""
        stream_lines = [
            json.dumps(
                {
                    "type": "assistant.message",
                    "data": {"content": "Task done."},
                }
            ).encode()
            + b"\n",
        ]
        proc = _make_mock_process(returncode=0, stdout_lines=stream_lines)
        engine = CopilotCLIEngine(diff_service=DiffService())

        with patch(
            "codehive.engine.copilot_cli_process.asyncio.create_subprocess_exec",
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
# Unit: CopilotCLIEngine - cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    """Tests for session cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_session_removes_state(self) -> None:
        """cleanup_session removes session state."""
        engine = CopilotCLIEngine(diff_service=DiffService())
        await engine.create_session(SESSION_ID)
        await engine.cleanup_session(SESSION_ID)
        assert SESSION_ID not in engine._sessions


# ---------------------------------------------------------------------------
# Integration: Engine wiring in _build_engine
# ---------------------------------------------------------------------------


class TestEngineWiring:
    """Tests for _build_engine copilot_cli engine type routing."""

    @pytest.mark.asyncio
    async def test_build_engine_returns_copilot_cli_engine(self) -> None:
        """_build_engine returns CopilotCLIEngine for 'copilot_cli'."""
        from codehive.api.routes.sessions import _build_engine

        engine = await _build_engine({"project_root": "/tmp"}, engine_type="copilot_cli")
        assert isinstance(engine, CopilotCLIEngine)


# ---------------------------------------------------------------------------
# Integration: Provider detection
# ---------------------------------------------------------------------------


class TestProviderDetection:
    """Tests for copilot provider in /api/providers endpoint."""

    @pytest.mark.asyncio
    async def test_copilot_available_when_cli_found(self, monkeypatch, tmp_path) -> None:
        """Copilot is available when copilot CLI is on PATH."""
        for key in list(__import__("os").environ):
            if key.startswith("CODEHIVE_"):
                monkeypatch.delenv(key, raising=False)
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ZAI_API_KEY", "OPENAI_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.chdir(tmp_path)

        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.side_effect = lambda name: (
                "/usr/bin/copilot" if name == "copilot" else None
            )
            result = await list_providers()

        copilot = next(p for p in result if p.name == "copilot")
        assert copilot.available is True
        assert copilot.type == "cli"
        assert "CLI found" in copilot.reason

    @pytest.mark.asyncio
    async def test_copilot_unavailable_when_cli_missing(self, monkeypatch, tmp_path) -> None:
        """Copilot is unavailable when copilot CLI is not on PATH."""
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

        copilot = next(p for p in result if p.name == "copilot")
        assert copilot.available is False
        assert copilot.reason == "CLI not found"

    @pytest.mark.asyncio
    async def test_provider_count_is_five(self, monkeypatch, tmp_path) -> None:
        """Provider list has 5 entries: claude, codex, openai, zai, copilot."""
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
