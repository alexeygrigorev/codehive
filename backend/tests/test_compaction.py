"""Tests for context compaction engine."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from codehive.core.compaction import (
    SUMMARIZATION_PROMPT,
    CompactionResult,
    ContextCompactor,
    _format_messages_for_summary,
    should_compact,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_messages(count: int) -> list[dict[str, Any]]:
    """Generate a list of alternating user/assistant messages."""
    messages: list[dict[str, Any]] = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append({"role": role, "content": f"Message {i}"})
    return messages


async def _mock_summarize(messages_text: str, model: str) -> str:
    """Simple mock summarizer that returns a fixed summary."""
    return "Summary of the conversation so far."


# ---------------------------------------------------------------------------
# Unit tests: ContextCompactor.compact()
# ---------------------------------------------------------------------------


class TestContextCompactorCompact:
    @pytest.mark.asyncio
    async def test_happy_path_10_messages_preserve_4(self):
        """Given 10 messages, preserve last 4, compact first 6."""
        messages = _make_messages(10)
        compactor = ContextCompactor(_mock_summarize)

        result = await compactor.compact(messages, model="test-model", preserve_last_n=4)

        assert result.compacted is True
        assert result.messages_compacted == 6
        assert result.messages_preserved == 4
        assert result.summary_text == "Summary of the conversation so far."
        # New messages: 1 summary + 4 preserved = 5
        assert len(result.messages) == 5
        # First message is the summary
        assert "[Previous conversation summary]" in result.messages[0]["content"]
        assert result.messages[0]["role"] == "user"
        # Last 4 messages preserved verbatim
        for i in range(4):
            assert result.messages[i + 1] == messages[6 + i]

    @pytest.mark.asyncio
    async def test_not_enough_messages(self):
        """Given 3 messages and preserve_last_n=4, return unchanged."""
        messages = _make_messages(3)
        compactor = ContextCompactor(_mock_summarize)

        result = await compactor.compact(messages, model="test-model", preserve_last_n=4)

        assert result.compacted is False
        assert result.messages_compacted == 0
        assert result.messages_preserved == 3
        assert result.summary_text == ""
        assert result.messages == messages

    @pytest.mark.asyncio
    async def test_exactly_n_plus_1_messages(self):
        """Given 5 messages and preserve_last_n=4, compact 1 message."""
        messages = _make_messages(5)
        compactor = ContextCompactor(_mock_summarize)

        result = await compactor.compact(messages, model="test-model", preserve_last_n=4)

        assert result.compacted is True
        assert result.messages_compacted == 1
        assert result.messages_preserved == 4
        assert len(result.messages) == 5  # 1 summary + 4 preserved

    @pytest.mark.asyncio
    async def test_summary_prompt_content(self):
        """Verify the summarization prompt includes key instructions."""
        assert "Key decisions" in SUMMARIZATION_PROMPT
        assert "Files being worked on" in SUMMARIZATION_PROMPT
        assert "pending actions" in SUMMARIZATION_PROMPT
        assert "Tool call results" in SUMMARIZATION_PROMPT

    @pytest.mark.asyncio
    async def test_tool_use_messages_included(self):
        """Messages with tool_use and tool_result blocks are included in summarization."""
        messages = [
            {"role": "user", "content": "Read the file"},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "read_file",
                        "input": {"path": "main.py"},
                        "id": "tool_1",
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_1",
                        "content": "print('hello')",
                    }
                ],
            },
            {"role": "assistant", "content": "I see the file."},
            {"role": "user", "content": "Thanks"},
            {"role": "assistant", "content": "You're welcome"},
            {"role": "user", "content": "More work"},
        ]

        captured_text: list[str] = []

        async def capturing_summarize(messages_text: str, model: str) -> str:
            captured_text.append(messages_text)
            return "Summary"

        compactor = ContextCompactor(capturing_summarize)
        result = await compactor.compact(messages, model="test-model", preserve_last_n=2)

        assert result.compacted is True
        text = captured_text[0]
        # Verify tool calls are represented
        assert "read_file" in text
        assert "main.py" in text or "path" in text
        assert "tool_result" in text.lower() or "Tool result" in text

    @pytest.mark.asyncio
    async def test_preserve_last_n_default(self):
        """Default preserve_last_n is 4."""
        messages = _make_messages(10)
        compactor = ContextCompactor(_mock_summarize)

        result = await compactor.compact(messages, model="test-model")

        assert result.messages_preserved == 4

    @pytest.mark.asyncio
    async def test_exactly_equal_to_preserve_returns_unchanged(self):
        """If exactly preserve_last_n messages, nothing to compact."""
        messages = _make_messages(4)
        compactor = ContextCompactor(_mock_summarize)

        result = await compactor.compact(messages, model="test-model", preserve_last_n=4)

        assert result.compacted is False
        assert result.messages == messages


# ---------------------------------------------------------------------------
# Unit tests: should_compact
# ---------------------------------------------------------------------------


class TestShouldCompact:
    def test_above_threshold(self):
        assert should_compact(170_000, 200_000, 0.80) is True

    def test_at_threshold(self):
        assert should_compact(160_000, 200_000, 0.80) is True

    def test_below_threshold(self):
        assert should_compact(100_000, 200_000, 0.80) is False

    def test_zero_context_window(self):
        assert should_compact(100, 0, 0.80) is False

    def test_custom_threshold(self):
        assert should_compact(140_000, 200_000, 0.70) is True
        assert should_compact(130_000, 200_000, 0.70) is False


# ---------------------------------------------------------------------------
# Unit tests: _format_messages_for_summary
# ---------------------------------------------------------------------------


class TestFormatMessages:
    def test_simple_string_content(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        text = _format_messages_for_summary(messages)
        assert "user: Hello" in text
        assert "assistant: Hi there" in text

    def test_structured_content_blocks(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me read that."},
                    {"type": "tool_use", "name": "read_file", "input": {"path": "x.py"}},
                ],
            }
        ]
        text = _format_messages_for_summary(messages)
        assert "read_file" in text
        assert "Let me read that" in text

    def test_function_call_content(self):
        """OpenAI-style function call items."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "function_call", "name": "run_shell", "arguments": '{"command":"ls"}'},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "function_call_output", "output": "file1.py\nfile2.py"},
                ],
            },
        ]
        text = _format_messages_for_summary(messages)
        assert "run_shell" in text
        assert "Function output" in text


# ---------------------------------------------------------------------------
# Unit tests: ZaiEngine compaction integration
# ---------------------------------------------------------------------------


class TestZaiEngineCompaction:
    @pytest.mark.asyncio
    async def test_compaction_triggers_at_threshold(self):
        """When usage >= 80% of context window, compaction is triggered."""
        from dataclasses import dataclass

        from codehive.engine.zai_engine import ZaiEngine

        # Build mocks
        client = AsyncMock()
        event_bus = AsyncMock()
        file_ops = MagicMock()
        shell_runner = MagicMock()
        git_ops = MagicMock()
        diff_service = MagicMock()

        engine = ZaiEngine(
            client=client,
            event_bus=event_bus,
            file_ops=file_ops,
            shell_runner=shell_runner,
            git_ops=git_ops,
            diff_service=diff_service,
        )

        session_id = uuid.uuid4()

        # Create session state with enough messages to compact
        await engine.create_session(session_id)
        state = engine._sessions[session_id]
        state.messages = _make_messages(10)

        # Mock the Anthropic response with high usage
        @dataclass
        class MockUsage:
            input_tokens: int = 170_000  # 85% of 200k
            output_tokens: int = 500

        @dataclass
        class MockTextBlock:
            type: str = "text"
            text: str = "Response"

        @dataclass
        class MockResponseObj:
            content: list = None  # type: ignore[assignment]
            usage: MockUsage = None  # type: ignore[assignment]
            model: str = "claude-sonnet-4-20250514"
            stop_reason: str = "end_turn"

            def __post_init__(self) -> None:
                if self.content is None:
                    self.content = [MockTextBlock()]
                if self.usage is None:
                    self.usage = MockUsage()

        response = MockResponseObj()

        # Mock stream
        class MockStreamCtx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            @property
            def text_stream(self):
                return _AsyncIter(["Response"])

            async def get_final_message(self):
                return response

        class _AsyncIter:
            def __init__(self, items):
                self._items = items
                self._i = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._i >= len(self._items):
                    raise StopAsyncIteration
                item = self._items[self._i]
                self._i += 1
                return item

        client.messages.stream = MagicMock(return_value=MockStreamCtx())

        # Mock the summarization call
        @dataclass
        class MockSumTextBlock:
            type: str = "text"
            text: str = "This is the compacted summary."

        summary_response = MagicMock()
        summary_response.content = [MockSumTextBlock()]
        client.messages.create = AsyncMock(return_value=summary_response)

        # Mock DB
        db = AsyncMock()
        session_row = MagicMock()
        session_row.config = {}
        session_row.project_id = uuid.uuid4()

        # db.get returns different things: first for usage record commit,
        # then for session lookup during compaction, then for knowledge
        async def mock_get(model_class, id_val):
            class_name = (
                model_class.__name__ if hasattr(model_class, "__name__") else str(model_class)
            )
            if class_name == "Session":
                return session_row
            return None

        db.get = AsyncMock(side_effect=mock_get)

        # Collect events
        events = []
        async for ev in engine.send_message(session_id, "test message", db=db):
            events.append(ev)

        # Verify compaction event was emitted
        compaction_events = [e for e in events if e.get("type") == "context.compacted"]
        assert len(compaction_events) == 1
        assert compaction_events[0]["messages_compacted"] > 0

        # Verify EventBus.publish was called with context.compacted
        publish_calls = event_bus.publish.call_args_list
        compaction_publishes = [
            c for c in publish_calls if len(c.args) >= 3 and c.args[2] == "context.compacted"
        ]
        assert len(compaction_publishes) == 1

    @pytest.mark.asyncio
    async def test_compaction_does_not_trigger_below_threshold(self):
        """When usage < 80% of context window, no compaction."""
        from dataclasses import dataclass

        from codehive.engine.zai_engine import ZaiEngine

        client = AsyncMock()
        event_bus = AsyncMock()

        engine = ZaiEngine(
            client=client,
            event_bus=event_bus,
            file_ops=MagicMock(),
            shell_runner=MagicMock(),
            git_ops=MagicMock(),
            diff_service=MagicMock(),
        )

        session_id = uuid.uuid4()
        await engine.create_session(session_id)
        state = engine._sessions[session_id]
        state.messages = _make_messages(10)

        @dataclass
        class MockUsage:
            input_tokens: int = 50_000  # 25% of 200k
            output_tokens: int = 500

        @dataclass
        class MockTextBlock:
            type: str = "text"
            text: str = "Response"

        @dataclass
        class MockResponseObj:
            content: list = None  # type: ignore[assignment]
            usage: MockUsage = None  # type: ignore[assignment]
            model: str = "claude-sonnet-4-20250514"

            def __post_init__(self) -> None:
                if self.content is None:
                    self.content = [MockTextBlock()]
                if self.usage is None:
                    self.usage = MockUsage()

        response = MockResponseObj()

        class MockStreamCtx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            @property
            def text_stream(self):
                return _AsyncIter(["Response"])

            async def get_final_message(self):
                return response

        class _AsyncIter:
            def __init__(self, items):
                self._items = items
                self._i = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._i >= len(self._items):
                    raise StopAsyncIteration
                item = self._items[self._i]
                self._i += 1
                return item

        client.messages.stream = MagicMock(return_value=MockStreamCtx())

        db = AsyncMock()
        session_row = MagicMock()
        session_row.config = {}
        session_row.project_id = uuid.uuid4()

        async def mock_get(model_class, id_val):
            class_name = (
                model_class.__name__ if hasattr(model_class, "__name__") else str(model_class)
            )
            if class_name == "Session":
                return session_row
            return None

        db.get = AsyncMock(side_effect=mock_get)

        events = []
        async for ev in engine.send_message(session_id, "test message", db=db):
            events.append(ev)

        compaction_events = [e for e in events if e.get("type") == "context.compacted"]
        assert len(compaction_events) == 0

    @pytest.mark.asyncio
    async def test_compaction_event_has_correct_metadata(self):
        """The context.compacted event published to EventBus has required fields."""
        from dataclasses import dataclass

        from codehive.engine.zai_engine import ZaiEngine

        client = AsyncMock()
        event_bus = AsyncMock()

        engine = ZaiEngine(
            client=client,
            event_bus=event_bus,
            file_ops=MagicMock(),
            shell_runner=MagicMock(),
            git_ops=MagicMock(),
            diff_service=MagicMock(),
        )

        session_id = uuid.uuid4()
        await engine.create_session(session_id)
        state = engine._sessions[session_id]
        state.messages = _make_messages(10)

        @dataclass
        class MockUsage:
            input_tokens: int = 170_000
            output_tokens: int = 500

        @dataclass
        class MockTextBlock:
            type: str = "text"
            text: str = "Response"

        @dataclass
        class MockResponseObj:
            content: list = None  # type: ignore[assignment]
            usage: MockUsage = None  # type: ignore[assignment]
            model: str = "claude-sonnet-4-20250514"

            def __post_init__(self) -> None:
                if self.content is None:
                    self.content = [MockTextBlock()]
                if self.usage is None:
                    self.usage = MockUsage()

        response = MockResponseObj()

        class MockStreamCtx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            @property
            def text_stream(self):
                return _AsyncIter(["Response"])

            async def get_final_message(self):
                return response

        class _AsyncIter:
            def __init__(self, items):
                self._items = items
                self._i = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._i >= len(self._items):
                    raise StopAsyncIteration
                item = self._items[self._i]
                self._i += 1
                return item

        client.messages.stream = MagicMock(return_value=MockStreamCtx())

        @dataclass
        class MockSumTextBlock:
            type: str = "text"
            text: str = "Compacted summary text."

        summary_response = MagicMock()
        summary_response.content = [MockSumTextBlock()]
        client.messages.create = AsyncMock(return_value=summary_response)

        db = AsyncMock()
        session_row = MagicMock()
        session_row.config = {"compaction_threshold": 0.80}
        session_row.project_id = uuid.uuid4()

        async def mock_get(model_class, id_val):
            class_name = (
                model_class.__name__ if hasattr(model_class, "__name__") else str(model_class)
            )
            if class_name == "Session":
                return session_row
            return None

        db.get = AsyncMock(side_effect=mock_get)

        events = []
        async for ev in engine.send_message(session_id, "test message", db=db):
            events.append(ev)

        # Check EventBus.publish was called with context.compacted and correct data
        publish_calls = event_bus.publish.call_args_list
        compaction_publishes = [
            c for c in publish_calls if len(c.args) >= 3 and c.args[2] == "context.compacted"
        ]
        assert len(compaction_publishes) == 1

        event_data = compaction_publishes[0].args[3]
        assert "messages_compacted" in event_data
        assert "messages_preserved" in event_data
        assert "summary_length" in event_data
        assert "threshold_percent" in event_data
        assert "summary_text" in event_data
        assert event_data["messages_compacted"] > 0
        assert event_data["threshold_percent"] == 85.0


# ---------------------------------------------------------------------------
# Unit tests: CodexEngine compaction integration
# ---------------------------------------------------------------------------


class TestCodexEngineCompaction:
    @pytest.mark.asyncio
    async def test_compaction_triggers_at_threshold(self):
        """When usage >= 80% of context window, CodexEngine triggers compaction."""
        from codehive.engine.codex import CodexEngine

        client = AsyncMock()
        event_bus = AsyncMock()

        engine = CodexEngine(
            client=client,
            event_bus=event_bus,
            file_ops=MagicMock(),
            shell_runner=MagicMock(),
            git_ops=MagicMock(),
            diff_service=MagicMock(),
        )

        session_id = uuid.uuid4()
        await engine.create_session(session_id)
        state = engine._sessions[session_id]
        state.input = _make_messages(10)

        # Build mock streaming events
        text_delta = MagicMock()
        text_delta.type = "response.output_text.delta"
        text_delta.delta = "Response text"

        usage = MagicMock()
        usage.input_tokens = 170_000  # 85%
        usage.output_tokens = 500

        response_obj = MagicMock()
        response_obj.usage = usage
        response_obj.model = "codex-mini-latest"
        response_obj.output = []  # No function calls

        completed_event = MagicMock()
        completed_event.type = "response.completed"
        completed_event.response = response_obj

        # Mock streaming: returns text delta then completed
        async def mock_stream():
            yield text_delta
            yield completed_event

        client.responses.create = AsyncMock(return_value=mock_stream())

        # Mock the OpenAI summarization call
        summary_output_text_block = MagicMock()
        summary_output_text_block.type = "output_text"
        summary_output_text_block.text = "Codex compacted summary."

        summary_message_item = MagicMock()
        summary_message_item.type = "message"
        summary_message_item.content = [summary_output_text_block]

        summary_response = MagicMock()
        summary_response.output = [summary_message_item]
        summary_response.output_text = "Codex compacted summary."

        # Second call to responses.create is for summarization
        call_count = 0

        async def create_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_stream()
            return summary_response

        client.responses.create = AsyncMock(side_effect=create_side_effect)

        db = AsyncMock()
        session_row = MagicMock()
        session_row.config = {}

        async def mock_get(model_class, id_val):
            class_name = (
                model_class.__name__ if hasattr(model_class, "__name__") else str(model_class)
            )
            if class_name == "Session":
                return session_row
            return None

        db.get = AsyncMock(side_effect=mock_get)

        events = []
        async for ev in engine.send_message(session_id, "test message", db=db):
            events.append(ev)

        compaction_events = [e for e in events if e.get("type") == "context.compacted"]
        assert len(compaction_events) == 1
        assert compaction_events[0]["messages_compacted"] > 0

    @pytest.mark.asyncio
    async def test_codex_compacted_messages_format(self):
        """After compaction, messages should still be in the right format."""
        from codehive.engine.codex import CodexEngine

        client = AsyncMock()
        event_bus = AsyncMock()

        engine = CodexEngine(
            client=client,
            event_bus=event_bus,
            file_ops=MagicMock(),
            shell_runner=MagicMock(),
            git_ops=MagicMock(),
            diff_service=MagicMock(),
        )

        session_id = uuid.uuid4()
        await engine.create_session(session_id)
        state = engine._sessions[session_id]
        state.input = _make_messages(10)

        # Mock high usage
        usage = MagicMock()
        usage.input_tokens = 170_000
        usage.output_tokens = 500

        response_obj = MagicMock()
        response_obj.usage = usage
        response_obj.model = "codex-mini-latest"
        response_obj.output = []

        text_delta = MagicMock()
        text_delta.type = "response.output_text.delta"
        text_delta.delta = "Done"

        completed = MagicMock()
        completed.type = "response.completed"
        completed.response = response_obj

        call_count = 0

        summary_output_text_block = MagicMock()
        summary_output_text_block.type = "output_text"
        summary_output_text_block.text = "Summary of conversation."

        summary_message_item = MagicMock()
        summary_message_item.type = "message"
        summary_message_item.content = [summary_output_text_block]

        summary_response = MagicMock()
        summary_response.output = [summary_message_item]
        summary_response.output_text = "Summary of conversation."

        async def mock_stream():
            yield text_delta
            yield completed

        async def create_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_stream()
            return summary_response

        client.responses.create = AsyncMock(side_effect=create_side_effect)

        db = AsyncMock()
        session_row = MagicMock()
        session_row.config = {}

        async def mock_get(model_class, id_val):
            class_name = (
                model_class.__name__ if hasattr(model_class, "__name__") else str(model_class)
            )
            if class_name == "Session":
                return session_row
            return None

        db.get = AsyncMock(side_effect=mock_get)

        events = []
        async for ev in engine.send_message(session_id, "test message", db=db):
            events.append(ev)

        # Verify the state.input was compacted and still has valid message format
        for msg in state.input:
            assert "role" in msg or "type" in msg
            if "role" in msg:
                assert msg["role"] in ("user", "assistant")


# ---------------------------------------------------------------------------
# Unit tests: CompactionResult dataclass
# ---------------------------------------------------------------------------


class TestCompactionResult:
    def test_default_compacted_true(self):
        result = CompactionResult(
            messages=[],
            messages_compacted=5,
            messages_preserved=4,
            summary_text="test",
        )
        assert result.compacted is True

    def test_explicit_compacted_false(self):
        result = CompactionResult(
            messages=[],
            messages_compacted=0,
            messages_preserved=3,
            summary_text="",
            compacted=False,
        )
        assert result.compacted is False
