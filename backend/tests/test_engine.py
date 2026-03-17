"""Tests for codehive.engine: EngineAdapter protocol and NativeEngine."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from codehive.engine import EngineAdapter, NativeEngine
from codehive.execution.diff import DiffService
from codehive.execution.file_ops import FileOps
from codehive.execution.git_ops import GitOps
from codehive.execution.shell import ShellRunner


# ---------------------------------------------------------------------------
# Helpers: mock Anthropic response objects
# ---------------------------------------------------------------------------


@dataclass
class MockTextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class MockToolUseBlock:
    type: str = "tool_use"
    id: str = "tool_1"
    name: str = "read_file"
    input: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.input is None:
            self.input = {}


@dataclass
class MockResponse:
    content: list = None  # type: ignore[assignment]
    stop_reason: str = "end_turn"

    def __post_init__(self) -> None:
        if self.content is None:
            self.content = []


class MockStream:
    """Mock for the Anthropic streaming context manager.

    Simulates ``async with client.messages.stream(**kwargs) as stream:``.
    The ``text_stream`` property yields text chunks from text blocks in the response.
    After exiting, ``get_final_message()`` returns the full MockResponse.
    """

    def __init__(self, response: MockResponse) -> None:
        self._response = response
        self._text_chunks: list[str] = []
        for block in response.content:
            if block.type == "text":
                # Split text into small chunks to simulate streaming
                text = block.text
                if len(text) <= 5:
                    self._text_chunks.append(text)
                else:
                    mid = len(text) // 2
                    self._text_chunks.append(text[:mid])
                    self._text_chunks.append(text[mid:])

    async def __aenter__(self) -> MockStream:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    @property
    def text_stream(self) -> _TextStreamIter:
        return _TextStreamIter(self._text_chunks)

    def get_final_message(self) -> MockResponse:
        return self._response


class _TextStreamIter:
    """Async iterator for text chunks."""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks
        self._index = 0

    def __aiter__(self) -> _TextStreamIter:
        return self

    async def __anext__(self) -> str:
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


def _make_engine(tmp_path: Path) -> tuple[NativeEngine, dict[str, Any]]:
    """Create a NativeEngine with mocked dependencies and return (engine, mocks)."""
    client = AsyncMock()
    event_bus = AsyncMock()
    file_ops = FileOps(tmp_path)
    shell_runner = ShellRunner()
    git_ops = GitOps(tmp_path)
    diff_service = DiffService()

    engine = NativeEngine(
        client=client,
        event_bus=event_bus,
        file_ops=file_ops,
        shell_runner=shell_runner,
        git_ops=git_ops,
        diff_service=diff_service,
    )

    return engine, {
        "client": client,
        "event_bus": event_bus,
        "file_ops": file_ops,
        "shell_runner": shell_runner,
        "git_ops": git_ops,
        "diff_service": diff_service,
    }


def _setup_stream_mock(mocks: dict[str, Any], responses: list[MockResponse] | MockResponse) -> None:
    """Configure the mock client to return MockStream instances.

    Accepts a single MockResponse or a list for multi-turn conversations.
    """
    if isinstance(responses, MockResponse):
        responses = [responses]

    call_count = 0

    def stream_side_effect(**kwargs: Any) -> MockStream:
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return MockStream(responses[idx])

    mocks["client"].messages.stream = MagicMock(side_effect=stream_side_effect)


async def _collect_events(aiter: Any) -> list[dict]:
    """Collect all events from an async iterator."""
    events = []
    async for event in aiter:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Unit: EngineAdapter Protocol
# ---------------------------------------------------------------------------


class TestEngineAdapterProtocol:
    def test_native_engine_satisfies_protocol(self, tmp_path: Path):
        """NativeEngine satisfies the EngineAdapter protocol."""
        engine, _ = _make_engine(tmp_path)
        assert isinstance(engine, EngineAdapter)

    def test_stub_missing_method_does_not_satisfy(self):
        """A stub class missing a method does NOT satisfy the protocol."""

        class IncompleteEngine:
            async def create_session(self, session_id: uuid.UUID) -> None:
                pass

            # Missing all other methods

        obj = IncompleteEngine()
        assert not isinstance(obj, EngineAdapter)


# ---------------------------------------------------------------------------
# Unit: Tool schema definitions
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    def test_tool_names(self, tmp_path: Path):
        """NativeEngine exposes the correct tool names."""
        engine, _ = _make_engine(tmp_path)
        names = [t["name"] for t in engine.tool_definitions]
        assert "read_file" in names
        assert "edit_file" in names
        assert "run_shell" in names
        assert "git_commit" in names
        assert "search_files" in names

    def test_tool_schema_structure(self, tmp_path: Path):
        """Each tool definition has name, description, and input_schema."""
        engine, _ = _make_engine(tmp_path)
        for tool in engine.tool_definitions:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            schema = tool["input_schema"]
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema


# ---------------------------------------------------------------------------
# Unit: Tool execution dispatch
# ---------------------------------------------------------------------------


class TestToolDispatch:
    @pytest.mark.asyncio
    async def test_read_file_dispatch(self, tmp_path: Path):
        """Dispatch read_file tool call delegates to FileOps.read_file."""
        (tmp_path / "test.txt").write_text("hello world")
        engine, mocks = _make_engine(tmp_path)
        result = await engine._execute_tool("read_file", {"path": "test.txt"})
        assert result["content"] == "hello world"
        assert "is_error" not in result

    @pytest.mark.asyncio
    async def test_edit_file_dispatch(self, tmp_path: Path):
        """Dispatch edit_file tool call delegates to FileOps.edit_file."""
        (tmp_path / "test.txt").write_text("hello old world")
        engine, _ = _make_engine(tmp_path)
        result = await engine._execute_tool(
            "edit_file",
            {"path": "test.txt", "old_text": "old", "new_text": "new"},
        )
        assert result["content"] == "hello new world"

    @pytest.mark.asyncio
    async def test_run_shell_dispatch(self, tmp_path: Path):
        """Dispatch run_shell tool call delegates to ShellRunner.run."""
        engine, _ = _make_engine(tmp_path)
        result = await engine._execute_tool(
            "run_shell",
            {"command": "echo hello"},
        )
        parsed = json.loads(result["content"])
        assert parsed["exit_code"] == 0
        assert "hello" in parsed["stdout"]

    @pytest.mark.asyncio
    async def test_git_commit_dispatch(self, tmp_path: Path):
        """Dispatch git_commit tool call delegates to GitOps.commit."""
        engine, mocks = _make_engine(tmp_path)
        # Mock the git_ops.commit since we don't have a real repo
        mocks["git_ops"].commit = AsyncMock(return_value="abc123" * 6 + "ab")
        engine._git_ops = mocks["git_ops"]
        result = await engine._execute_tool("git_commit", {"message": "test commit"})
        assert "Committed:" in result["content"]
        mocks["git_ops"].commit.assert_awaited_once_with("test commit")

    @pytest.mark.asyncio
    async def test_search_files_dispatch(self, tmp_path: Path):
        """Dispatch search_files tool call delegates to FileOps.list_files."""
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")
        engine, _ = _make_engine(tmp_path)
        result = await engine._execute_tool("search_files", {"pattern": "*.py"})
        files = json.loads(result["content"])
        assert len(files) == 2
        assert all(f.endswith(".py") for f in files)

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, tmp_path: Path):
        """Unknown tool name returns an error result."""
        engine, _ = _make_engine(tmp_path)
        result = await engine._execute_tool("nonexistent_tool", {})
        assert result.get("is_error") is True
        assert "Unknown tool" in result["content"]

    @pytest.mark.asyncio
    async def test_tool_exception_returns_error(self, tmp_path: Path):
        """Tool that raises an exception returns an error result."""
        engine, _ = _make_engine(tmp_path)
        # read_file on nonexistent file should raise FileNotFoundError
        result = await engine._execute_tool("read_file", {"path": "nonexistent.txt"})
        assert result.get("is_error") is True
        assert "FileNotFoundError" in result["content"]


# ---------------------------------------------------------------------------
# Unit: Conversation loop (send_message)
# ---------------------------------------------------------------------------


class TestConversationLoop:
    @pytest.mark.asyncio
    async def test_simple_text_response(self, tmp_path: Path):
        """Mock Anthropic to return a text response (no tool use)."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        # Mock: simple text response via streaming
        _setup_stream_mock(
            mocks,
            MockResponse(content=[MockTextBlock(text="Hello, I can help!")]),
        )

        events = await _collect_events(engine.send_message(session_id, "Hi"))

        # Should have user message.created + delta events + assistant message.created
        msg_created = [e for e in events if e["type"] == "message.created"]
        assert len(msg_created) == 2
        assert msg_created[0]["role"] == "user"
        assert msg_created[1]["role"] == "assistant"
        assert msg_created[1]["content"] == "Hello, I can help!"

        # Should also have message.delta events
        deltas = [e for e in events if e["type"] == "message.delta"]
        assert len(deltas) >= 1
        assert all(d["role"] == "assistant" for d in deltas)

    @pytest.mark.asyncio
    async def test_tool_use_then_text(self, tmp_path: Path):
        """Mock: tool_use response, then text response on follow-up."""
        (tmp_path / "readme.txt").write_text("file contents here")
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            [
                MockResponse(
                    content=[
                        MockToolUseBlock(
                            id="tool_1",
                            name="read_file",
                            input={"path": "readme.txt"},
                        )
                    ]
                ),
                MockResponse(content=[MockTextBlock(text="The file says: file contents here")]),
            ],
        )

        events = await _collect_events(engine.send_message(session_id, "Read the file"))

        # Check event sequence
        types = [e["type"] for e in events]
        assert "message.created" in types  # user
        assert "tool.call.started" in types
        assert "tool.call.finished" in types

        # tool.call.finished should contain the file contents
        tool_finished = [e for e in events if e["type"] == "tool.call.finished"][0]
        assert tool_finished["result"]["content"] == "file contents here"

        # Final assistant message
        assistant_msgs = [
            e for e in events if e["type"] == "message.created" and e.get("role") == "assistant"
        ]
        assert len(assistant_msgs) == 1
        assert "file contents here" in assistant_msgs[0]["content"]

    @pytest.mark.asyncio
    async def test_two_tool_use_blocks_in_single_response(self, tmp_path: Path):
        """Mock: two tool_use blocks in one response, both executed."""
        (tmp_path / "a.txt").write_text("content a")
        (tmp_path / "b.txt").write_text("content b")
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            [
                MockResponse(
                    content=[
                        MockToolUseBlock(
                            id="tool_1",
                            name="read_file",
                            input={"path": "a.txt"},
                        ),
                        MockToolUseBlock(
                            id="tool_2",
                            name="read_file",
                            input={"path": "b.txt"},
                        ),
                    ]
                ),
                MockResponse(content=[MockTextBlock(text="Read both files.")]),
            ],
        )

        events = await _collect_events(engine.send_message(session_id, "Read both"))

        started_events = [e for e in events if e["type"] == "tool.call.started"]
        finished_events = [e for e in events if e["type"] == "tool.call.finished"]
        assert len(started_events) == 2
        assert len(finished_events) == 2
        assert finished_events[0]["result"]["content"] == "content a"
        assert finished_events[1]["result"]["content"] == "content b"

    @pytest.mark.asyncio
    async def test_tool_exception_handled(self, tmp_path: Path):
        """Tool that raises an error: error is caught, loop continues."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            [
                MockResponse(
                    content=[
                        MockToolUseBlock(
                            id="tool_1",
                            name="read_file",
                            input={"path": "nonexistent.txt"},
                        )
                    ]
                ),
                MockResponse(content=[MockTextBlock(text="File not found, sorry.")]),
            ],
        )

        events = await _collect_events(engine.send_message(session_id, "Read file"))

        # tool.call.finished should have is_error in result
        finished = [e for e in events if e["type"] == "tool.call.finished"][0]
        assert finished["result"].get("is_error") is True
        assert "FileNotFoundError" in finished["result"]["content"]

        # The loop continued and produced a final assistant message
        assistant_msgs = [
            e for e in events if e["type"] == "message.created" and e.get("role") == "assistant"
        ]
        assert len(assistant_msgs) == 1


# ---------------------------------------------------------------------------
# Unit: Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    @pytest.mark.asyncio
    async def test_events_published_to_bus(self, tmp_path: Path):
        """EventBus.publish is called for message.created, message.delta, and tool events."""
        (tmp_path / "test.txt").write_text("content")
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            [
                MockResponse(
                    content=[
                        MockToolUseBlock(
                            id="tool_1",
                            name="read_file",
                            input={"path": "test.txt"},
                        )
                    ]
                ),
                MockResponse(content=[MockTextBlock(text="Done.")]),
            ],
        )

        db_mock = MagicMock()
        await _collect_events(engine.send_message(session_id, "Read it", db=db_mock))

        # EventBus.publish should be called for each event type
        publish_calls = mocks["event_bus"].publish.call_args_list
        event_types = [call.args[2] for call in publish_calls]
        assert "message.created" in event_types  # user message
        assert "tool.call.started" in event_types
        assert "tool.call.finished" in event_types
        # Check session_id was passed
        for call in publish_calls:
            assert call.args[1] == session_id


# ---------------------------------------------------------------------------
# Unit: Pause / Resume
# ---------------------------------------------------------------------------


class TestPauseResume:
    @pytest.mark.asyncio
    async def test_pause_stops_loop(self, tmp_path: Path):
        """When paused, send_message yields a paused event and stops."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)
        await engine.pause(session_id)

        events = await _collect_events(engine.send_message(session_id, "Hello"))

        assert len(events) == 1
        assert events[0]["type"] == "session.paused"

    @pytest.mark.asyncio
    async def test_resume_allows_loop(self, tmp_path: Path):
        """After resume, send_message proceeds normally."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        await engine.pause(session_id)
        await engine.resume(session_id)

        _setup_stream_mock(
            mocks,
            MockResponse(content=[MockTextBlock(text="Resumed!")]),
        )

        events = await _collect_events(engine.send_message(session_id, "Hello"))

        msg_events = [e for e in events if e["type"] == "message.created"]
        assert len(msg_events) == 2
        assert msg_events[1]["content"] == "Resumed!"


# ---------------------------------------------------------------------------
# Unit: get_diff
# ---------------------------------------------------------------------------


class TestGetDiff:
    @pytest.mark.asyncio
    async def test_get_diff_delegates_to_diff_service(self, tmp_path: Path):
        """get_diff returns data from DiffService.get_session_changes."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()

        # Track some changes in the diff service
        mocks["diff_service"].track_change(str(session_id), "file.py", "+new line")

        result = await engine.get_diff(session_id)
        assert result == {"file.py": "+new line"}

    @pytest.mark.asyncio
    async def test_get_diff_empty_session(self, tmp_path: Path):
        """get_diff returns empty dict for a session with no changes."""
        engine, _ = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        result = await engine.get_diff(session_id)
        assert result == {}


# ---------------------------------------------------------------------------
# Unit: start_task
# ---------------------------------------------------------------------------


class TestStartTask:
    @pytest.mark.asyncio
    async def test_start_task_with_instructions(self, tmp_path: Path):
        """start_task feeds task instructions into send_message."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        task_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            MockResponse(content=[MockTextBlock(text="Task completed.")]),
        )

        events = await _collect_events(
            engine.start_task(session_id, task_id, task_instructions="Build the feature")
        )

        # The user message should be the task instructions
        user_msg = [e for e in events if e["type"] == "message.created" and e.get("role") == "user"]
        assert len(user_msg) == 1
        assert user_msg[0]["content"] == "Build the feature"

    @pytest.mark.asyncio
    async def test_start_task_with_fetcher(self, tmp_path: Path):
        """start_task uses task_fetcher callback when no instructions given."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        task_id = uuid.uuid4()
        await engine.create_session(session_id)

        engine._task_fetcher = AsyncMock(return_value={"instructions": "Fetched instructions"})

        _setup_stream_mock(
            mocks,
            MockResponse(content=[MockTextBlock(text="Done.")]),
        )

        events = await _collect_events(engine.start_task(session_id, task_id))

        user_msg = [e for e in events if e["type"] == "message.created" and e.get("role") == "user"]
        assert user_msg[0]["content"] == "Fetched instructions"
        engine._task_fetcher.assert_awaited_once_with(task_id)
