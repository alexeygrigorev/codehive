"""Tests for compaction configuration: compaction_enabled and compaction_preserve_last_n."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_messages(count: int) -> list[dict[str, Any]]:
    """Generate alternating user/assistant messages."""
    messages: list[dict[str, Any]] = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append({"role": role, "content": f"Message {i}"})
    return messages


async def _mock_summarize(messages_text: str, model: str) -> str:
    return "Summary of conversation."


# Common mock infrastructure for engine tests


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


class _AsyncIter:
    def __init__(self, items: list) -> None:
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


class MockStreamCtx:
    def __init__(self, response: MockResponseObj | None = None):
        self._response = response or MockResponseObj()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    @property
    def text_stream(self):
        return _AsyncIter(["Response"])

    async def get_final_message(self):
        return self._response


def _make_zai_mocks(session_config: dict):
    """Build common mocks for ZaiEngine tests."""
    client = AsyncMock()
    event_bus = AsyncMock()

    response = MockResponseObj()
    client.messages.stream = MagicMock(return_value=MockStreamCtx(response))

    @dataclass
    class MockSumTextBlock:
        type: str = "text"
        text: str = "Compacted summary."

    summary_response = MagicMock()
    summary_response.content = [MockSumTextBlock()]
    client.messages.create = AsyncMock(return_value=summary_response)

    db = AsyncMock()
    session_row = MagicMock()
    session_row.config = session_config
    session_row.project_id = uuid.uuid4()

    async def mock_get(model_class, id_val):
        class_name = model_class.__name__ if hasattr(model_class, "__name__") else str(model_class)
        if class_name == "Session":
            return session_row
        return None

    db.get = AsyncMock(side_effect=mock_get)

    return client, event_bus, db


# ---------------------------------------------------------------------------
# Tests: compaction_enabled config
# ---------------------------------------------------------------------------


class TestCompactionEnabled:
    @pytest.mark.asyncio
    async def test_compaction_skipped_when_disabled(self):
        """When compaction_enabled=false, compaction does not trigger even above threshold."""
        from codehive.engine.zai_engine import ZaiEngine

        client, event_bus, db = _make_zai_mocks({"compaction_enabled": False})

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

        events = []
        async for ev in engine.send_message(session_id, "test", db=db):
            events.append(ev)

        compaction_events = [e for e in events if e.get("type") == "context.compacted"]
        assert len(compaction_events) == 0

    @pytest.mark.asyncio
    async def test_compaction_runs_when_enabled_explicitly(self):
        """When compaction_enabled=true, compaction triggers normally."""
        from codehive.engine.zai_engine import ZaiEngine

        client, event_bus, db = _make_zai_mocks({"compaction_enabled": True})

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

        events = []
        async for ev in engine.send_message(session_id, "test", db=db):
            events.append(ev)

        compaction_events = [e for e in events if e.get("type") == "context.compacted"]
        assert len(compaction_events) == 1

    @pytest.mark.asyncio
    async def test_compaction_defaults_to_enabled(self):
        """When compaction_enabled is not in config, compaction is enabled by default."""
        from codehive.engine.zai_engine import ZaiEngine

        client, event_bus, db = _make_zai_mocks({})

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

        events = []
        async for ev in engine.send_message(session_id, "test", db=db):
            events.append(ev)

        compaction_events = [e for e in events if e.get("type") == "context.compacted"]
        assert len(compaction_events) == 1


# ---------------------------------------------------------------------------
# Tests: compaction_preserve_last_n config
# ---------------------------------------------------------------------------


class TestCompactionPreserveLastN:
    @pytest.mark.asyncio
    async def test_preserve_last_n_passed_to_compactor(self):
        """When compaction_preserve_last_n is set, it is used instead of the default."""
        from codehive.engine.zai_engine import ZaiEngine

        client, event_bus, db = _make_zai_mocks({"compaction_preserve_last_n": 6})

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

        events = []
        async for ev in engine.send_message(session_id, "test", db=db):
            events.append(ev)

        compaction_events = [e for e in events if e.get("type") == "context.compacted"]
        assert len(compaction_events) == 1

        # Verify: with 10 messages and preserve_last_n=6, should compact 4
        event_data = compaction_events[0]
        assert event_data["messages_compacted"] > 0

        # Check the EventBus.publish call data
        publish_calls = event_bus.publish.call_args_list
        compaction_publishes = [
            c for c in publish_calls if len(c.args) >= 3 and c.args[2] == "context.compacted"
        ]
        assert len(compaction_publishes) == 1
        pub_data = compaction_publishes[0].args[3]
        assert pub_data["messages_preserved"] == 6
        # 10 initial + 1 user message from send_message = 11; 11 - 6 = 5 compacted
        assert pub_data["messages_compacted"] == 5


# ---------------------------------------------------------------------------
# Tests: CodexEngine compaction config
# ---------------------------------------------------------------------------


class TestCodexCompactionConfig:
    @pytest.mark.asyncio
    async def test_codex_compaction_skipped_when_disabled(self):
        """CodexEngine respects compaction_enabled=false."""
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
        usage.input_tokens = 170_000
        usage.output_tokens = 500

        response_obj = MagicMock()
        response_obj.usage = usage
        response_obj.model = "codex-mini-latest"
        response_obj.output = []

        completed_event = MagicMock()
        completed_event.type = "response.completed"
        completed_event.response = response_obj

        async def mock_stream():
            yield text_delta
            yield completed_event

        client.responses.create = AsyncMock(return_value=mock_stream())

        db = AsyncMock()
        session_row = MagicMock()
        session_row.config = {"compaction_enabled": False}

        async def mock_get(model_class, id_val):
            class_name = (
                model_class.__name__ if hasattr(model_class, "__name__") else str(model_class)
            )
            if class_name == "Session":
                return session_row
            return None

        db.get = AsyncMock(side_effect=mock_get)

        events = []
        async for ev in engine.send_message(session_id, "test", db=db):
            events.append(ev)

        compaction_events = [e for e in events if e.get("type") == "context.compacted"]
        assert len(compaction_events) == 0

    @pytest.mark.asyncio
    async def test_codex_preserve_last_n_passed(self):
        """CodexEngine passes compaction_preserve_last_n to compactor."""
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

        text_delta = MagicMock()
        text_delta.type = "response.output_text.delta"
        text_delta.delta = "Response text"

        usage = MagicMock()
        usage.input_tokens = 170_000
        usage.output_tokens = 500

        response_obj = MagicMock()
        response_obj.usage = usage
        response_obj.model = "codex-mini-latest"
        response_obj.output = []

        completed_event = MagicMock()
        completed_event.type = "response.completed"
        completed_event.response = response_obj

        summary_output_text_block = MagicMock()
        summary_output_text_block.type = "output_text"
        summary_output_text_block.text = "Summary."

        summary_message_item = MagicMock()
        summary_message_item.type = "message"
        summary_message_item.content = [summary_output_text_block]

        summary_response = MagicMock()
        summary_response.output = [summary_message_item]
        summary_response.output_text = "Summary."

        call_count = 0

        async def mock_stream():
            yield text_delta
            yield completed_event

        async def create_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_stream()
            return summary_response

        client.responses.create = AsyncMock(side_effect=create_side_effect)

        db = AsyncMock()
        session_row = MagicMock()
        session_row.config = {"compaction_preserve_last_n": 6}

        async def mock_get(model_class, id_val):
            class_name = (
                model_class.__name__ if hasattr(model_class, "__name__") else str(model_class)
            )
            if class_name == "Session":
                return session_row
            return None

        db.get = AsyncMock(side_effect=mock_get)

        events = []
        async for ev in engine.send_message(session_id, "test", db=db):
            events.append(ev)

        compaction_events = [e for e in events if e.get("type") == "context.compacted"]
        assert len(compaction_events) == 1

        # Verify preserved count
        publish_calls = event_bus.publish.call_args_list
        compaction_publishes = [
            c for c in publish_calls if len(c.args) >= 3 and c.args[2] == "context.compacted"
        ]
        assert len(compaction_publishes) == 1
        pub_data = compaction_publishes[0].args[3]
        assert pub_data["messages_preserved"] == 6


# ---------------------------------------------------------------------------
# Tests: Events endpoint type filter
# ---------------------------------------------------------------------------


class TestEventsTypeFilter:
    @pytest.mark.asyncio
    async def test_get_events_with_type_filter(self):
        """EventBus.get_events filters by event_type when provided."""
        from datetime import datetime, timezone

        from sqlalchemy import event
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from codehive.core.events import EventBus
        from codehive.db.models import Base, Project
        from codehive.db.models import Session as SessionModel

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as db:
            # Create project and session
            proj = Project(name="test", knowledge={}, created_at=datetime.now(timezone.utc))
            db.add(proj)
            await db.commit()
            await db.refresh(proj)

            sess = SessionModel(
                project_id=proj.id,
                name="test-session",
                engine="native",
                mode="execution",
                status="idle",
                config={},
                created_at=datetime.now(timezone.utc),
            )
            db.add(sess)
            await db.commit()
            await db.refresh(sess)

            # Publish events of different types
            mock_redis = AsyncMock()
            mock_redis.publish = AsyncMock(return_value=1)
            bus = EventBus(redis=mock_redis)

            await bus.publish(db, sess.id, "message.created", {"content": "hello"})
            await bus.publish(db, sess.id, "context.compacted", {"messages_compacted": 5})
            await bus.publish(db, sess.id, "message.created", {"content": "world"})
            await bus.publish(db, sess.id, "context.compacted", {"messages_compacted": 3})

            # Get all events
            all_events = await bus.get_events(db, sess.id, limit=50)
            assert len(all_events) == 4

            # Get only context.compacted
            compacted = await bus.get_events(db, sess.id, limit=50, event_type="context.compacted")
            assert len(compacted) == 2
            assert all(e.type == "context.compacted" for e in compacted)

            # Get only message.created
            messages = await bus.get_events(db, sess.id, limit=50, event_type="message.created")
            assert len(messages) == 2
            assert all(e.type == "message.created" for e in messages)

            # Get non-existent type
            empty = await bus.get_events(db, sess.id, limit=50, event_type="nonexistent.type")
            assert len(empty) == 0

        await engine.dispose()
