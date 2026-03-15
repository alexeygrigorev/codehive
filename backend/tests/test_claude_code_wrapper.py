"""Tests for Claude Code CLI wrapper and event parser.

All tests use mocked subprocess -- no real ``claude`` CLI invocation.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codehive.engine.claude_code import ClaudeCodeProcess
from codehive.engine.claude_code_parser import ClaudeCodeParser

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SESSION_ID = uuid.uuid4()


@pytest.fixture
def parser() -> ClaudeCodeParser:
    return ClaudeCodeParser()


@pytest.fixture
def process() -> ClaudeCodeProcess:
    return ClaudeCodeProcess(session_id=SESSION_ID)


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestClaudeCodeParser:
    """Unit tests for ClaudeCodeParser.parse_line()."""

    def test_parse_assistant_text_message(self, parser: ClaudeCodeParser) -> None:
        """Parse a stream-json line with an assistant text message."""
        line = json.dumps(
            {"type": "assistant", "content": [{"type": "text", "text": "Hello, world!"}]}
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        evt = events[0]
        assert evt["type"] == "message.created"
        assert evt["role"] == "assistant"
        assert evt["content"] == "Hello, world!"
        assert evt["session_id"] == str(SESSION_ID)

    def test_parse_assistant_text_string_content(self, parser: ClaudeCodeParser) -> None:
        """Parse assistant message where content is a plain string."""
        line = json.dumps({"type": "assistant", "content": "Direct string content"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["content"] == "Direct string content"
        assert events[0]["type"] == "message.created"

    def test_parse_tool_use(self, parser: ClaudeCodeParser) -> None:
        """Parse a tool_use block into tool.call.started event."""
        line = json.dumps(
            {
                "type": "tool_use",
                "name": "read_file",
                "input": {"path": "src/main.py"},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        evt = events[0]
        assert evt["type"] == "tool.call.started"
        assert evt["tool_name"] == "read_file"
        assert evt["tool_input"] == {"path": "src/main.py"}
        assert evt["session_id"] == str(SESSION_ID)

    def test_parse_tool_result(self, parser: ClaudeCodeParser) -> None:
        """Parse a tool_result into tool.call.finished event."""
        line = json.dumps(
            {
                "type": "tool_result",
                "name": "run_shell",
                "content": "command output here",
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        evt = events[0]
        assert evt["type"] == "tool.call.finished"
        assert evt["tool_name"] == "run_shell"
        assert evt["result"] == "command output here"
        assert evt["session_id"] == str(SESSION_ID)

    def test_parse_tool_result_with_file_change(self, parser: ClaudeCodeParser) -> None:
        """Parse a tool_result for edit_file emits both finished and file.changed."""
        line = json.dumps(
            {
                "type": "tool_result",
                "name": "edit_file",
                "content": "File edited successfully",
                "path": "src/main.py",
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 2
        assert events[0]["type"] == "tool.call.finished"
        assert events[1]["type"] == "file.changed"
        assert events[1]["path"] == "src/main.py"

    def test_parse_malformed_json(self, parser: ClaudeCodeParser) -> None:
        """Malformed JSON returns empty list, no exception."""
        events = parser.parse_line("this is not json {{{", SESSION_ID)
        assert events == []

    def test_parse_empty_string(self, parser: ClaudeCodeParser) -> None:
        """Empty string returns empty list."""
        assert parser.parse_line("", SESSION_ID) == []

    def test_parse_whitespace_only(self, parser: ClaudeCodeParser) -> None:
        """Whitespace-only string returns empty list."""
        assert parser.parse_line("   \n  ", SESSION_ID) == []

    def test_parse_unrecognized_type(self, parser: ClaudeCodeParser) -> None:
        """Unrecognised message type returns empty list."""
        line = json.dumps({"type": "some_future_type", "data": "foo"})
        events = parser.parse_line(line, SESSION_ID)
        assert events == []

    def test_parse_error_message(self, parser: ClaudeCodeParser) -> None:
        """Error messages produce session.error events."""
        line = json.dumps({"type": "error", "error": "Rate limit exceeded"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "session.error"
        assert events[0]["error"] == "Rate limit exceeded"
        assert events[0]["session_id"] == str(SESSION_ID)

    def test_parse_system_message(self, parser: ClaudeCodeParser) -> None:
        """System messages produce session.error events."""
        line = json.dumps({"type": "system", "message": "System overload"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "session.error"
        assert events[0]["error"] == "System overload"

    def test_all_events_have_required_keys(self, parser: ClaudeCodeParser) -> None:
        """Every event returned must include session_id and type."""
        lines = [
            json.dumps({"type": "assistant", "content": "hi"}),
            json.dumps({"type": "tool_use", "name": "x", "input": {}}),
            json.dumps({"type": "tool_result", "name": "x", "content": "ok"}),
            json.dumps({"type": "error", "error": "bad"}),
        ]
        for line in lines:
            for evt in parser.parse_line(line, SESSION_ID):
                assert "type" in evt, f"Missing 'type' in event from: {line}"
                assert "session_id" in evt, f"Missing 'session_id' in event from: {line}"

    def test_parse_result_message(self, parser: ClaudeCodeParser) -> None:
        """Result message type is mapped to message.created."""
        line = json.dumps({"type": "result", "content": [{"type": "text", "text": "Final answer"}]})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.created"
        assert events[0]["content"] == "Final answer"

    def test_parse_non_dict_json(self, parser: ClaudeCodeParser) -> None:
        """A JSON array (non-object) returns empty list."""
        events = parser.parse_line("[1, 2, 3]", SESSION_ID)
        assert events == []

    def test_parse_content_block_delta(self, parser: ClaudeCodeParser) -> None:
        """content_block_delta with text_delta is parsed as message.created."""
        line = json.dumps(
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "streaming chunk"},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.created"
        assert events[0]["content"] == "streaming chunk"


# ---------------------------------------------------------------------------
# Process manager tests
# ---------------------------------------------------------------------------


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


class TestClaudeCodeProcess:
    """Unit tests for ClaudeCodeProcess with mocked subprocess."""

    @pytest.mark.asyncio
    async def test_start_spawns_with_correct_flags(self) -> None:
        """start() calls create_subprocess_exec with the right CLI flags."""
        proc = _make_mock_process(returncode=None)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = ClaudeCodeProcess(session_id=SESSION_ID)
            await p.start()

            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert args[0] == "claude"
            assert "--print" in args
            assert "--output-format" in args
            assert "stream-json" in args
            assert "--input-format" in args

    @pytest.mark.asyncio
    async def test_start_with_custom_cli_path(self) -> None:
        """Configurable CLI path is used in the spawn command."""
        proc = _make_mock_process(returncode=None)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = ClaudeCodeProcess(session_id=SESSION_ID, cli_path="/usr/local/bin/claude")
            await p.start()

            args = mock_exec.call_args[0]
            assert args[0] == "/usr/local/bin/claude"

    @pytest.mark.asyncio
    async def test_start_with_extra_flags(self) -> None:
        """Extra CLI flags are passed through to the subprocess."""
        proc = _make_mock_process(returncode=None)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = ClaudeCodeProcess(
                session_id=SESSION_ID,
                extra_flags=["--model", "opus", "--permission-mode", "auto"],
            )
            await p.start()

            args = mock_exec.call_args[0]
            assert "--model" in args
            assert "opus" in args
            assert "--permission-mode" in args
            assert "auto" in args

    @pytest.mark.asyncio
    async def test_send_writes_to_stdin(self) -> None:
        """send() writes newline-delimited JSON to the process stdin."""
        proc = _make_mock_process(returncode=None)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess(session_id=SESSION_ID)
            await p.start()
            await p.send("Hello Claude")

            proc.stdin.write.assert_called_once()
            written = proc.stdin.write.call_args[0][0]
            payload = json.loads(written.decode().strip())
            assert payload["type"] == "user"
            assert payload["content"] == "Hello Claude"
            proc.stdin.drain.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_raises_when_not_running(self) -> None:
        """send() raises RuntimeError when process is not started."""
        p = ClaudeCodeProcess(session_id=SESSION_ID)
        with pytest.raises(RuntimeError, match="not running"):
            await p.send("hello")

    @pytest.mark.asyncio
    async def test_stop_terminates_process(self) -> None:
        """stop() calls terminate on the subprocess."""
        proc = _make_mock_process(returncode=None)

        # After terminate, returncode stays None until wait
        # Simulate: wait sets returncode
        async def fake_wait():
            proc.returncode = 0

        proc.wait = AsyncMock(side_effect=fake_wait)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess(session_id=SESSION_ID)
            await p.start()

            assert p.is_alive()
            await p.stop()

            proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_alive_running(self) -> None:
        """is_alive() returns True for a running process."""
        proc = _make_mock_process(returncode=None)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess(session_id=SESSION_ID)
            await p.start()
            assert p.is_alive() is True

    @pytest.mark.asyncio
    async def test_is_alive_not_started(self) -> None:
        """is_alive() returns False before start()."""
        p = ClaudeCodeProcess(session_id=SESSION_ID)
        assert p.is_alive() is False

    @pytest.mark.asyncio
    async def test_is_alive_after_exit(self) -> None:
        """is_alive() returns False after process exits."""
        proc = _make_mock_process(returncode=0)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess(session_id=SESSION_ID)
            await p.start()
            assert p.is_alive() is False

    @pytest.mark.asyncio
    async def test_read_stdout_line(self) -> None:
        """Stdout lines can be read from the process."""
        line_data = json.dumps({"type": "assistant", "content": "hi"})
        proc = _make_mock_process(
            returncode=None,
            stdout_lines=[f"{line_data}\n".encode()],
        )

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess(session_id=SESSION_ID)
            await p.start()

            line = await p.read_stdout_line()
            assert line == line_data

            # EOF returns None
            eof = await p.read_stdout_line()
            assert eof is None

    @pytest.mark.asyncio
    async def test_check_for_crash_returns_session_failed(self) -> None:
        """When process exits with non-zero code, check_for_crash returns session.failed."""
        proc = _make_mock_process(returncode=1, stderr_data=b"Segfault or something")

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess(session_id=SESSION_ID)
            await p.start()

            event = await p.check_for_crash()
            assert event is not None
            assert event["type"] == "session.failed"
            assert event["session_id"] == str(SESSION_ID)
            assert event["exit_code"] == 1
            assert "Segfault" in event["error"]

    @pytest.mark.asyncio
    async def test_check_for_crash_returns_none_when_running(self) -> None:
        """check_for_crash returns None when the process is still running."""
        proc = _make_mock_process(returncode=None)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess(session_id=SESSION_ID)
            await p.start()

            assert await p.check_for_crash() is None

    @pytest.mark.asyncio
    async def test_check_for_crash_returns_none_on_clean_exit(self) -> None:
        """check_for_crash returns None when process exits with code 0."""
        proc = _make_mock_process(returncode=0)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess(session_id=SESSION_ID)
            await p.start()

            assert await p.check_for_crash() is None

    @pytest.mark.asyncio
    async def test_working_dir_passed_to_subprocess(self) -> None:
        """working_dir is passed as cwd to the subprocess."""
        proc = _make_mock_process(returncode=None)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = ClaudeCodeProcess(session_id=SESSION_ID, working_dir="/home/user/project")
            await p.start()

            kwargs = mock_exec.call_args[1]
            assert kwargs["cwd"] == "/home/user/project"


# ---------------------------------------------------------------------------
# Integration: Process + Parser together
# ---------------------------------------------------------------------------


class TestProcessParserIntegration:
    """Feed mocked stream-json through process stdout and parse into events."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self) -> None:
        """Read stdout lines from the process and parse them into codehive events."""
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

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess(session_id=SESSION_ID)
            await p.start()

            all_events: list[dict] = []
            while True:
                line = await p.read_stdout_line()
                if line is None:
                    break
                events = p.parser.parse_line(line, p.session_id)
                all_events.extend(events)

        assert len(all_events) == 4
        assert all_events[0]["type"] == "message.created"
        assert all_events[0]["content"] == "Let me help you."
        assert all_events[1]["type"] == "tool.call.started"
        assert all_events[1]["tool_name"] == "read_file"
        assert all_events[2]["type"] == "tool.call.finished"
        assert all_events[2]["tool_name"] == "read_file"
        assert all_events[3]["type"] == "message.created"
        assert all_events[3]["content"] == "Done!"

        # All events have session_id
        for evt in all_events:
            assert evt["session_id"] == str(SESSION_ID)
