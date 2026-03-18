"""Tests for CodexEngine: tool schema conversion, conversation loop, streaming, etc."""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from codehive.engine.codex import (
    CodexEngine,
    TOOL_DEFINITIONS_ANTHROPIC,
    convert_tool_to_openai,
    get_openai_tools,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(
    client: Any = None,
    event_bus: Any = None,
    file_ops: Any = None,
    shell_runner: Any = None,
    git_ops: Any = None,
    diff_service: Any = None,
    model: str = "codex-mini-latest",
) -> CodexEngine:
    return CodexEngine(
        client=client or MagicMock(),
        event_bus=event_bus,
        file_ops=file_ops or MagicMock(),
        shell_runner=shell_runner or MagicMock(),
        git_ops=git_ops or MagicMock(),
        diff_service=diff_service or MagicMock(),
        model=model,
    )


def _make_response_completed_event(
    output_items: list[Any] | None = None,
    input_tokens: int = 10,
    output_tokens: int = 20,
    model: str = "codex-mini-latest",
) -> MagicMock:
    """Create a mock response.completed SSE event."""
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens

    response = MagicMock()
    response.usage = usage
    response.model = model
    response.output = output_items or []

    event = MagicMock()
    event.type = "response.completed"
    event.response = response
    return event


def _make_text_delta_event(text: str) -> MagicMock:
    """Create a mock response.output_text.delta SSE event."""
    event = MagicMock()
    event.type = "response.output_text.delta"
    event.delta = text
    return event


def _make_function_call_item(name: str, arguments: dict, call_id: str = "call_123") -> MagicMock:
    """Create a mock function_call output item."""
    item = MagicMock()
    item.type = "function_call"
    item.call_id = call_id
    item.name = name
    item.arguments = json.dumps(arguments)
    return item


class _AsyncIterator:
    """Async iterator from a list of items."""

    def __init__(self, items: list) -> None:
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration


# ---------------------------------------------------------------------------
# Tests: Tool schema conversion
# ---------------------------------------------------------------------------


class TestToolSchemaConversion:
    """Test converting Codehive/Anthropic tool definitions to OpenAI format."""

    def test_convert_read_file(self):
        tool = TOOL_DEFINITIONS_ANTHROPIC[0]
        assert tool["name"] == "read_file"

        result = convert_tool_to_openai(tool)

        assert result["type"] == "function"
        assert result["function"]["name"] == "read_file"
        assert result["function"]["description"] == tool["description"]
        assert result["function"]["parameters"] == tool["input_schema"]
        assert "path" in result["function"]["parameters"]["properties"]
        assert result["function"]["parameters"]["required"] == ["path"]

    def test_convert_edit_file(self):
        tool = TOOL_DEFINITIONS_ANTHROPIC[1]
        assert tool["name"] == "edit_file"

        result = convert_tool_to_openai(tool)

        assert result["type"] == "function"
        assert result["function"]["name"] == "edit_file"
        params = result["function"]["parameters"]
        assert set(params["required"]) == {"path", "old_text", "new_text"}

    def test_convert_run_shell(self):
        tool = next(t for t in TOOL_DEFINITIONS_ANTHROPIC if t["name"] == "run_shell")
        result = convert_tool_to_openai(tool)

        assert result["function"]["name"] == "run_shell"
        assert "command" in result["function"]["parameters"]["properties"]

    def test_convert_all_tools(self):
        results = get_openai_tools()
        assert len(results) == len(TOOL_DEFINITIONS_ANTHROPIC)
        for r in results:
            assert r["type"] == "function"
            assert "name" in r["function"]
            assert "parameters" in r["function"]

    def test_all_tool_names_preserved(self):
        expected_names = {t["name"] for t in TOOL_DEFINITIONS_ANTHROPIC}
        actual_names = {t["function"]["name"] for t in get_openai_tools()}
        assert expected_names == actual_names

    def test_required_fields_preserved(self):
        for tool in TOOL_DEFINITIONS_ANTHROPIC:
            result = convert_tool_to_openai(tool)
            assert result["function"]["parameters"]["required"] == tool["input_schema"]["required"]


# ---------------------------------------------------------------------------
# Tests: Session lifecycle
# ---------------------------------------------------------------------------


class TestSessionLifecycle:
    @pytest.mark.asyncio
    async def test_create_session(self):
        engine = _make_engine()
        sid = uuid.uuid4()
        await engine.create_session(sid)
        assert sid in engine._sessions

    @pytest.mark.asyncio
    async def test_pause_resume(self):
        engine = _make_engine()
        sid = uuid.uuid4()
        await engine.create_session(sid)

        await engine.pause(sid)
        assert engine._sessions[sid].paused is True

        await engine.resume(sid)
        assert engine._sessions[sid].paused is False

    @pytest.mark.asyncio
    async def test_send_message_on_paused_session(self):
        engine = _make_engine()
        sid = uuid.uuid4()
        await engine.create_session(sid)
        await engine.pause(sid)

        events = []
        async for event in engine.send_message(sid, "hello"):
            events.append(event)

        assert len(events) == 1
        assert events[0]["type"] == "session.paused"

    @pytest.mark.asyncio
    async def test_pause_creates_session_if_missing(self):
        engine = _make_engine()
        sid = uuid.uuid4()
        await engine.pause(sid)
        assert engine._sessions[sid].paused is True


# ---------------------------------------------------------------------------
# Tests: Conversation loop (mocked client)
# ---------------------------------------------------------------------------


class TestConversationLoop:
    @pytest.mark.asyncio
    async def test_text_only_response(self):
        """Model returns text only -- verify message.created event."""
        client = MagicMock()
        stream_events = [
            _make_text_delta_event("Hello "),
            _make_text_delta_event("world!"),
            _make_response_completed_event(output_items=[]),
        ]
        client.responses.create = AsyncMock(return_value=_AsyncIterator(stream_events))

        engine = _make_engine(client=client)
        sid = uuid.uuid4()

        events = []
        async for event in engine.send_message(sid, "Hi"):
            events.append(event)

        # user message.created + 2 deltas + assistant message.created
        types = [e["type"] for e in events]
        assert types[0] == "message.created"
        assert events[0]["role"] == "user"
        assert "message.delta" in types
        assert types[-1] == "message.created"
        assert events[-1]["role"] == "assistant"
        assert events[-1]["content"] == "Hello world!"

    @pytest.mark.asyncio
    async def test_streaming_deltas(self):
        """Verify streaming deltas yield message.delta events."""
        client = MagicMock()
        stream_events = [
            _make_text_delta_event("chunk1"),
            _make_text_delta_event("chunk2"),
            _make_text_delta_event("chunk3"),
            _make_response_completed_event(output_items=[]),
        ]
        client.responses.create = AsyncMock(return_value=_AsyncIterator(stream_events))

        engine = _make_engine(client=client)
        sid = uuid.uuid4()

        events = []
        async for event in engine.send_message(sid, "Hi"):
            events.append(event)

        delta_events = [e for e in events if e["type"] == "message.delta"]
        assert len(delta_events) == 3
        assert delta_events[0]["content"] == "chunk1"
        assert delta_events[1]["content"] == "chunk2"
        assert delta_events[2]["content"] == "chunk3"

    @pytest.mark.asyncio
    async def test_tool_use_then_text(self):
        """Model calls a tool then returns text -- verify tool events."""
        client = MagicMock()
        file_ops = MagicMock()
        file_ops.read_file = AsyncMock(return_value="file contents here")

        # First call: model returns a function call
        fc_item = _make_function_call_item("read_file", {"path": "README.md"}, "call_abc")
        first_response = [
            _make_response_completed_event(output_items=[fc_item]),
        ]

        # Second call: model returns text
        second_response = [
            _make_text_delta_event("Summary of README"),
            _make_response_completed_event(output_items=[]),
        ]

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _AsyncIterator(first_response)
            return _AsyncIterator(second_response)

        client.responses.create = mock_create

        engine = _make_engine(client=client, file_ops=file_ops)
        sid = uuid.uuid4()

        events = []
        async for event in engine.send_message(sid, "Read the README"):
            events.append(event)

        types = [e["type"] for e in events]
        assert "tool.call.started" in types
        assert "tool.call.finished" in types
        assert "message.created" in types

        # Check tool call events
        started = next(e for e in events if e["type"] == "tool.call.started")
        assert started["tool_name"] == "read_file"
        assert started["tool_use_id"] == "call_abc"

        finished = next(e for e in events if e["type"] == "tool.call.finished")
        assert finished["tool_name"] == "read_file"
        assert finished["result"]["content"] == "file contents here"

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self):
        """Model makes multiple tool calls in one response."""
        client = MagicMock()
        file_ops = MagicMock()
        file_ops.read_file = AsyncMock(return_value="content")
        file_ops.list_files = AsyncMock(return_value=["a.py", "b.py"])

        fc1 = _make_function_call_item("read_file", {"path": "a.py"}, "call_1")
        fc2 = _make_function_call_item("search_files", {"pattern": "*.py"}, "call_2")

        first_response = [
            _make_response_completed_event(output_items=[fc1, fc2]),
        ]
        second_response = [
            _make_text_delta_event("Done"),
            _make_response_completed_event(output_items=[]),
        ]

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _AsyncIterator(first_response)
            return _AsyncIterator(second_response)

        client.responses.create = mock_create

        engine = _make_engine(client=client, file_ops=file_ops)
        sid = uuid.uuid4()

        events = []
        async for event in engine.send_message(sid, "Analyze"):
            events.append(event)

        started_events = [e for e in events if e["type"] == "tool.call.started"]
        finished_events = [e for e in events if e["type"] == "tool.call.finished"]
        assert len(started_events) == 2
        assert len(finished_events) == 2


# ---------------------------------------------------------------------------
# Tests: Tool execution
# ---------------------------------------------------------------------------


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_read_file(self):
        file_ops = MagicMock()
        file_ops.read_file = AsyncMock(return_value="hello world")

        engine = _make_engine(file_ops=file_ops)
        result = await engine._execute_tool("read_file", {"path": "test.txt"})
        assert result["content"] == "hello world"
        assert "is_error" not in result

    @pytest.mark.asyncio
    async def test_run_shell(self):
        shell_runner = MagicMock()
        shell_result = MagicMock()
        shell_result.stdout = "output"
        shell_result.stderr = ""
        shell_result.exit_code = 0
        shell_result.timed_out = False
        shell_runner.run = AsyncMock(return_value=shell_result)

        file_ops = MagicMock()
        file_ops._root = MagicMock()
        file_ops._root.__truediv__ = MagicMock(return_value=MagicMock())

        engine = _make_engine(file_ops=file_ops, shell_runner=shell_runner)
        result = await engine._execute_tool("run_shell", {"command": "ls"})

        parsed = json.loads(result["content"])
        assert parsed["exit_code"] == 0
        assert parsed["stdout"] == "output"

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        engine = _make_engine()
        result = await engine._execute_tool("nonexistent", {})
        assert "Unknown tool" in result["content"]
        assert result["is_error"] is True

    @pytest.mark.asyncio
    async def test_tool_exception_handled(self):
        file_ops = MagicMock()
        file_ops.read_file = AsyncMock(side_effect=FileNotFoundError("not found"))

        engine = _make_engine(file_ops=file_ops)
        result = await engine._execute_tool("read_file", {"path": "missing.txt"})
        assert "Error" in result["content"]
        assert result["is_error"] is True

    @pytest.mark.asyncio
    async def test_git_commit(self):
        git_ops = MagicMock()
        git_ops.commit = AsyncMock(return_value="abc123")

        engine = _make_engine(git_ops=git_ops)
        result = await engine._execute_tool("git_commit", {"message": "test commit"})
        assert "abc123" in result["content"]

    @pytest.mark.asyncio
    async def test_search_files(self):
        file_ops = MagicMock()
        file_ops.list_files = AsyncMock(return_value=["a.py", "b.py"])

        engine = _make_engine(file_ops=file_ops)
        result = await engine._execute_tool("search_files", {"pattern": "*.py"})
        parsed = json.loads(result["content"])
        assert parsed == ["a.py", "b.py"]

    @pytest.mark.asyncio
    async def test_edit_file(self):
        file_ops = MagicMock()
        file_ops.edit_file = AsyncMock(return_value="File updated")

        engine = _make_engine(file_ops=file_ops)
        result = await engine._execute_tool(
            "edit_file",
            {"path": "test.py", "old_text": "old", "new_text": "new"},
        )
        assert result["content"] == "File updated"


# ---------------------------------------------------------------------------
# Tests: Usage tracking
# ---------------------------------------------------------------------------


class TestUsageTracking:
    @pytest.mark.asyncio
    async def test_usage_recorded_on_response(self):
        """Usage data is written to DB after response.completed."""
        client = MagicMock()
        stream_events = [
            _make_text_delta_event("Hi"),
            _make_response_completed_event(input_tokens=100, output_tokens=50),
        ]
        client.responses.create = AsyncMock(return_value=_AsyncIterator(stream_events))

        db = MagicMock()
        db.add = MagicMock()
        db.commit = AsyncMock()

        engine = _make_engine(client=client, event_bus=None)
        sid = uuid.uuid4()

        events = []
        async for event in engine.send_message(sid, "Hi", db=db):
            events.append(event)

        # Verify db.add was called with a UsageRecord
        assert db.add.called
        usage_record = db.add.call_args[0][0]
        assert usage_record.input_tokens == 100
        assert usage_record.output_tokens == 50


# ---------------------------------------------------------------------------
# Tests: get_diff
# ---------------------------------------------------------------------------


class TestGetDiff:
    @pytest.mark.asyncio
    async def test_get_diff_delegates_to_diff_service(self):
        diff_service = MagicMock()
        diff_service.get_session_changes = MagicMock(return_value={"file.py": "diff"})

        engine = _make_engine(diff_service=diff_service)
        sid = uuid.uuid4()

        result = await engine.get_diff(sid)
        assert result == {"file.py": "diff"}
        diff_service.get_session_changes.assert_called_once_with(str(sid))
