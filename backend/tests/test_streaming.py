"""Tests for issue #83: Streaming support.

Covers NativeEngine streaming (message.delta events), ClaudeCodeParser delta mapping,
and TUI bindings.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from codehive.engine.claude_code_parser import ClaudeCodeParser
from codehive.engine.native import NativeEngine
from codehive.execution.diff import DiffService
from codehive.execution.file_ops import FileOps
from codehive.execution.git_ops import GitOps
from codehive.execution.shell import ShellRunner


# ---------------------------------------------------------------------------
# Helpers
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
    """Mock for the Anthropic streaming context manager."""

    def __init__(self, response: MockResponse, chunks: list[str] | None = None) -> None:
        self._response = response
        if chunks is not None:
            self._text_chunks = chunks
        else:
            self._text_chunks = []
            for block in response.content:
                if block.type == "text":
                    text = block.text
                    if len(text) <= 3:
                        self._text_chunks.append(text)
                    else:
                        # Split into 3 chunks for better test coverage
                        third = len(text) // 3
                        self._text_chunks.append(text[:third])
                        self._text_chunks.append(text[third : 2 * third])
                        self._text_chunks.append(text[2 * third :])

    async def __aenter__(self) -> MockStream:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    @property
    def text_stream(self) -> _TextStreamIter:
        return _TextStreamIter(self._text_chunks)

    async def get_final_message(self) -> MockResponse:
        return self._response


class _TextStreamIter:
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


def _setup_stream_mock(
    mocks: dict[str, Any],
    responses: list[MockResponse] | MockResponse,
    chunks_list: list[list[str]] | None = None,
) -> None:
    if isinstance(responses, MockResponse):
        responses = [responses]

    call_count = 0

    def stream_side_effect(**kwargs: Any) -> MockStream:
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        chunks = None
        if chunks_list is not None and call_count < len(chunks_list):
            chunks = chunks_list[call_count]
        call_count += 1
        return MockStream(responses[idx], chunks=chunks)

    mocks["client"].messages.stream = MagicMock(side_effect=stream_side_effect)


async def _collect_events(aiter: Any) -> list[dict]:
    events = []
    async for event in aiter:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Unit: NativeEngine streaming
# ---------------------------------------------------------------------------

SESSION_ID = uuid.uuid4()


class TestNativeEngineStreaming:
    @pytest.mark.asyncio
    async def test_yields_delta_events_before_created(self, tmp_path: Path):
        """send_message yields multiple message.delta events followed by message.created."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            MockResponse(content=[MockTextBlock(text="Hello world!")]),
            chunks_list=[["Hello", " world", "!"]],
        )

        events = await _collect_events(engine.send_message(session_id, "Hi"))

        deltas = [e for e in events if e["type"] == "message.delta"]
        created = [
            e for e in events if e["type"] == "message.created" and e.get("role") == "assistant"
        ]

        # Multiple delta events
        assert len(deltas) == 3
        assert deltas[0]["content"] == "Hello"
        assert deltas[1]["content"] == " world"
        assert deltas[2]["content"] == "!"
        assert all(d["role"] == "assistant" for d in deltas)

        # One final message.created with full text
        assert len(created) == 1
        assert created[0]["content"] == "Hello world!"

        # Deltas come before the created event
        delta_indices = [i for i, e in enumerate(events) if e["type"] == "message.delta"]
        created_idx = next(
            i
            for i, e in enumerate(events)
            if e["type"] == "message.created" and e.get("role") == "assistant"
        )
        assert all(di < created_idx for di in delta_indices)

    @pytest.mark.asyncio
    async def test_tool_use_with_pre_tool_text_deltas(self, tmp_path: Path):
        """Stream with tool_use blocks: text deltas before tool calls still fire."""
        (tmp_path / "f.txt").write_text("data")
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            [
                # First turn: text + tool_use
                MockResponse(
                    content=[
                        MockTextBlock(text="Let me read that"),
                        MockToolUseBlock(id="t1", name="read_file", input={"path": "f.txt"}),
                    ]
                ),
                # Second turn: final text
                MockResponse(content=[MockTextBlock(text="The file contains data")]),
            ],
            chunks_list=[["Let me ", "read that"], ["The file ", "contains data"]],
        )

        events = await _collect_events(engine.send_message(session_id, "Read f.txt"))

        # First turn: deltas for pre-tool text
        first_deltas = []
        for e in events:
            if e["type"] == "message.delta":
                first_deltas.append(e)
            elif e["type"] == "tool.call.started":
                break

        assert len(first_deltas) >= 1
        combined_first = "".join(d["content"] for d in first_deltas)
        assert "Let me " in combined_first

        # Tool events still fire
        assert any(e["type"] == "tool.call.started" for e in events)
        assert any(e["type"] == "tool.call.finished" for e in events)

        # Final message.created exists
        final_created = [
            e for e in events if e["type"] == "message.created" and e.get("role") == "assistant"
        ]
        assert len(final_created) == 1
        assert "contains data" in final_created[0]["content"]

    @pytest.mark.asyncio
    async def test_delta_events_published_to_event_bus(self, tmp_path: Path):
        """EventBus.publish is called with message.delta for each chunk."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            MockResponse(content=[MockTextBlock(text="AB")]),
            chunks_list=[["A", "B"]],
        )

        db_mock = MagicMock()
        await _collect_events(engine.send_message(session_id, "go", db=db_mock))

        publish_calls = mocks["event_bus"].publish.call_args_list
        delta_publish_calls = [c for c in publish_calls if c.args[2] == "message.delta"]
        assert len(delta_publish_calls) == 2
        assert delta_publish_calls[0].args[3] == {"role": "assistant", "content": "A"}
        assert delta_publish_calls[1].args[3] == {"role": "assistant", "content": "B"}

        # Also verify message.created is published
        created_publish = [c for c in publish_calls if c.args[2] == "message.created"]
        # user + assistant
        assert len(created_publish) == 2

    @pytest.mark.asyncio
    async def test_message_created_still_yielded_for_backwards_compat(self, tmp_path: Path):
        """message.created is still yielded as the final event (backwards compat)."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            MockResponse(content=[MockTextBlock(text="done")]),
            chunks_list=[["done"]],
        )

        events = await _collect_events(engine.send_message(session_id, "x"))

        types = [e["type"] for e in events]
        # Must have both delta and created for assistant
        assert "message.delta" in types
        assert "message.created" in types

        # The last event should be message.created (assistant)
        assistant_events = [e for e in events if e.get("role") == "assistant"]
        assert assistant_events[-1]["type"] == "message.created"


# ---------------------------------------------------------------------------
# Unit: ClaudeCodeParser delta mapping
# ---------------------------------------------------------------------------


class TestClaudeCodeParserDelta:
    @pytest.fixture
    def parser(self) -> ClaudeCodeParser:
        return ClaudeCodeParser()

    def test_content_block_delta_yields_message_delta(self, parser: ClaudeCodeParser) -> None:
        """content_block_delta with text_delta yields message.delta, not message.created."""
        line = json.dumps(
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "chunk"},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.delta"
        assert events[0]["role"] == "assistant"
        assert events[0]["content"] == "chunk"
        assert events[0]["session_id"] == str(SESSION_ID)

    def test_assistant_message_yields_message_created(self, parser: ClaudeCodeParser) -> None:
        """assistant message type still yields message.created."""
        line = json.dumps({"type": "assistant", "content": "full response"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.created"

    def test_result_message_yields_message_created(self, parser: ClaudeCodeParser) -> None:
        """result message type still yields message.created."""
        line = json.dumps({"type": "result", "content": "final answer"})
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 1
        assert events[0]["type"] == "message.created"

    def test_empty_text_delta_yields_nothing(self, parser: ClaudeCodeParser) -> None:
        """content_block_delta with empty text yields no events."""
        line = json.dumps(
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": ""},
            }
        )
        events = parser.parse_line(line, SESSION_ID)
        assert len(events) == 0


# ---------------------------------------------------------------------------
# Unit: TUI bindings
# ---------------------------------------------------------------------------


class TestTUIBindings:
    def test_code_app_has_required_bindings(self) -> None:
        """CodeApp BINDINGS contains entries for ctrl+q, ctrl+l, ctrl+n."""
        from codehive.clients.terminal.code_app import CodeApp

        binding_keys = [b[0] for b in CodeApp.BINDINGS]
        assert "ctrl+q" in binding_keys
        assert "ctrl+l" in binding_keys
        assert "ctrl+n" in binding_keys

    def test_code_app_has_quit_binding(self) -> None:
        """CodeApp BINDINGS contains ctrl+q for quit."""
        from codehive.clients.terminal.code_app import CodeApp

        binding_keys = [b[0] for b in CodeApp.BINDINGS]
        assert "ctrl+q" in binding_keys

    def test_code_app_bindings_have_descriptions(self) -> None:
        """All bindings have a description (third element)."""
        from codehive.clients.terminal.code_app import CodeApp

        for binding in CodeApp.BINDINGS:
            assert len(binding) >= 3, f"Binding {binding[0]} missing description"
            assert binding[2], f"Binding {binding[0]} has empty description"


# ---------------------------------------------------------------------------
# Unit: TUI markdown widget
# ---------------------------------------------------------------------------


class TestTUIMarkdownWidget:
    def test_assistant_markdown_widget_exists(self) -> None:
        """_AssistantMarkdown widget class exists and is a Markdown subclass."""
        from codehive.clients.terminal.code_app import _AssistantMarkdown

        from textual.widgets import Markdown

        assert issubclass(_AssistantMarkdown, Markdown)
