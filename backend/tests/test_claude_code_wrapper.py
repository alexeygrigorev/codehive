"""Tests for Claude Code CLI wrapper (fire-and-forget) and event parser.

All tests use mocked subprocess -- no real ``claude`` CLI invocation.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codehive.engine.claude_code import ClaudeCodeProcess, ClaudeProcessError
from codehive.engine.claude_code_parser import ClaudeCodeParser

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SESSION_ID = uuid.uuid4()


@pytest.fixture
def parser() -> ClaudeCodeParser:
    return ClaudeCodeParser()


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

    def test_parse_system_message_without_init(self, parser: ClaudeCodeParser) -> None:
        """System messages without subtype=init produce session.error events."""
        line = json.dumps({"type": "system", "message": "System overload"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "session.error"
        assert events[0]["error"] == "System overload"

    def test_parse_system_init(self, parser: ClaudeCodeParser) -> None:
        """system.init event is parsed into session.started with claude_session_id and model."""
        line = json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "session_id": "claude-sess-abc123",
                "model": "claude-sonnet-4-20250514",
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        evt = events[0]
        assert evt["type"] == "session.started"
        assert evt["session_id"] == str(SESSION_ID)
        assert evt["claude_session_id"] == "claude-sess-abc123"
        assert evt["model"] == "claude-sonnet-4-20250514"

    def test_parse_system_init_missing_fields(self, parser: ClaudeCodeParser) -> None:
        """system.init with missing optional fields uses defaults."""
        line = json.dumps({"type": "system", "subtype": "init"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["claude_session_id"] == ""
        assert events[0]["model"] == ""

    def test_all_events_have_required_keys(self, parser: ClaudeCodeParser) -> None:
        """Every event returned must include session_id and type."""
        lines = [
            json.dumps({"type": "assistant", "content": "hi"}),
            json.dumps({"type": "tool_use", "name": "x", "input": {}}),
            json.dumps({"type": "tool_result", "name": "x", "content": "ok"}),
            json.dumps({"type": "error", "error": "bad"}),
            json.dumps({"type": "system", "subtype": "init", "session_id": "s1", "model": "m"}),
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
        """content_block_delta with text_delta is parsed as message.delta."""
        line = json.dumps(
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "streaming chunk"},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.delta"
        assert events[0]["content"] == "streaming chunk"


# ---------------------------------------------------------------------------
# Process manager tests (fire-and-forget model)
# ---------------------------------------------------------------------------


def _make_mock_process(
    returncode: int = 0,
    stdout_lines: list[bytes] | None = None,
    stderr_data: bytes = b"",
) -> MagicMock:
    """Create a mock asyncio.subprocess.Process for fire-and-forget model."""
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

    # wait
    proc.wait = AsyncMock(return_value=returncode)

    return proc


class TestClaudeCodeProcess:
    """Unit tests for ClaudeCodeProcess fire-and-forget model."""

    @pytest.mark.asyncio
    async def test_run_spawns_with_correct_flags(self) -> None:
        """run() calls create_subprocess_exec with -p and correct flags (no --input-format)."""
        proc = _make_mock_process(returncode=0)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = ClaudeCodeProcess()
            async for _ in p.run("Hello"):
                pass

            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert args[0] == "claude"
            assert "-p" in args
            assert "Hello" in args
            assert "--output-format" in args
            assert "stream-json" in args
            assert "--verbose" in args
            # Must NOT have old interactive flags
            assert "--input-format" not in args
            assert "--print" not in args

    @pytest.mark.asyncio
    async def test_run_with_resume_session_id(self) -> None:
        """run() with resume_session_id adds --resume flag."""
        proc = _make_mock_process(returncode=0)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = ClaudeCodeProcess()
            async for _ in p.run("Continue", resume_session_id="sess-abc"):
                pass

            args = mock_exec.call_args[0]
            assert "--resume" in args
            assert "sess-abc" in args

    @pytest.mark.asyncio
    async def test_run_without_resume_has_no_resume_flag(self) -> None:
        """run() without resume_session_id does not add --resume."""
        proc = _make_mock_process(returncode=0)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = ClaudeCodeProcess()
            async for _ in p.run("Hello"):
                pass

            args = mock_exec.call_args[0]
            assert "--resume" not in args

    @pytest.mark.asyncio
    async def test_run_yields_stdout_lines(self) -> None:
        """run() yields each non-empty stdout line."""
        lines = [b'{"type":"assistant","content":"hi"}\n', b'{"type":"result","content":"done"}\n']
        proc = _make_mock_process(returncode=0, stdout_lines=lines)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess()
            collected = []
            async for line in p.run("Hello"):
                collected.append(line)

            assert len(collected) == 2
            assert '"assistant"' in collected[0]
            assert '"result"' in collected[1]

    @pytest.mark.asyncio
    async def test_run_returns_cleanly_on_exit_code_0(self) -> None:
        """run() completes without error on exit code 0."""
        proc = _make_mock_process(returncode=0, stdout_lines=[b"line\n"])

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess()
            lines = []
            async for line in p.run("Hello"):
                lines.append(line)
            assert lines == ["line"]

    @pytest.mark.asyncio
    async def test_run_raises_on_non_zero_exit(self) -> None:
        """run() raises ClaudeProcessError on non-zero exit code."""
        proc = _make_mock_process(returncode=1, stderr_data=b"Segfault")

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess()
            with pytest.raises(ClaudeProcessError) as exc_info:
                async for _ in p.run("Hello"):
                    pass
            assert exc_info.value.exit_code == 1
            assert "Segfault" in exc_info.value.stderr

    @pytest.mark.asyncio
    async def test_run_with_working_dir(self) -> None:
        """working_dir is passed as cwd to the subprocess."""
        proc = _make_mock_process(returncode=0)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = ClaudeCodeProcess(working_dir="/home/user/project")
            async for _ in p.run("Hello"):
                pass

            kwargs = mock_exec.call_args[1]
            assert kwargs["cwd"] == "/home/user/project"

    @pytest.mark.asyncio
    async def test_run_with_custom_cli_path(self) -> None:
        """Configurable CLI path is used."""
        proc = _make_mock_process(returncode=0)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = ClaudeCodeProcess(cli_path="/usr/local/bin/claude")
            async for _ in p.run("Hello"):
                pass

            args = mock_exec.call_args[0]
            assert args[0] == "/usr/local/bin/claude"

    @pytest.mark.asyncio
    async def test_run_with_extra_flags(self) -> None:
        """Extra CLI flags are passed through."""
        proc = _make_mock_process(returncode=0)

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_exec:
            p = ClaudeCodeProcess(extra_flags=["--model", "opus"])
            async for _ in p.run("Hello"):
                pass

            args = mock_exec.call_args[0]
            assert "--model" in args
            assert "opus" in args


# ---------------------------------------------------------------------------
# Integration: Process + Parser together
# ---------------------------------------------------------------------------


class TestProcessParserIntegration:
    """Feed mocked stream-json through process run() and parse into events."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self) -> None:
        """Read stdout lines from process.run() and parse them into codehive events."""
        stream_lines = [
            json.dumps(
                {"type": "system", "subtype": "init", "session_id": "cs-123", "model": "opus"}
            ).encode()
            + b"\n",
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
        parser = ClaudeCodeParser()

        with patch(
            "codehive.engine.claude_code.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            p = ClaudeCodeProcess()
            all_events: list[dict] = []
            async for line in p.run("Help me"):
                events = parser.parse_line(line, SESSION_ID)
                all_events.extend(events)

        assert len(all_events) == 5
        assert all_events[0]["type"] == "session.started"
        assert all_events[0]["claude_session_id"] == "cs-123"
        assert all_events[1]["type"] == "message.created"
        assert all_events[1]["content"] == "Let me help you."
        assert all_events[2]["type"] == "tool.call.started"
        assert all_events[2]["tool_name"] == "read_file"
        assert all_events[3]["type"] == "tool.call.finished"
        assert all_events[3]["tool_name"] == "read_file"
        assert all_events[4]["type"] == "message.created"
        assert all_events[4]["content"] == "Done!"

        # All events have session_id
        for evt in all_events:
            assert evt["session_id"] == str(SESSION_ID)
