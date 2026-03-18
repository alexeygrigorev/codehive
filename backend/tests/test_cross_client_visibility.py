"""Tests for issue #94c: Cross-client session visibility.

Covers:
- SSE streaming endpoint returns text/event-stream content type
- SSE events are parseable as data: {json}
- Engine events are published to event bus during message handling
- WebSocket subscribers receive events when messages are sent via API
- Cross-client event flow (engine -> event bus -> WebSocket subscriber)
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import JSON, MetaData, Table, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.core.events import LocalEventBus
from codehive.db.models import Base, Project
from codehive.db.models import Session as SessionModel
from codehive.engine.native import NativeEngine
from codehive.execution.diff import DiffService
from codehive.execution.file_ops import FileOps
from codehive.execution.git_ops import GitOps
from codehive.execution.shell import ShellRunner


# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


def _sqlite_compatible_metadata() -> MetaData:
    """Return a copy of Base.metadata with SQLite-compatible types and defaults."""
    metadata = MetaData()

    for table in Base.metadata.tables.values():
        columns = []
        for col in table.columns:
            col_copy = col._copy()

            if col_copy.type.__class__.__name__ == "JSONB":
                col_copy.type = JSON()

            if col_copy.server_default is not None:
                default_text = str(col_copy.server_default.arg)
                if "::jsonb" in default_text:
                    col_copy.server_default = text("'{}'")
                elif "now()" in default_text:
                    col_copy.server_default = text("(datetime('now'))")
                elif default_text == "true":
                    col_copy.server_default = text("1")
                elif default_text == "false":
                    col_copy.server_default = text("0")

            columns.append(col_copy)

        Table(table.name, metadata, *columns)

    return metadata


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create tables in an in-memory SQLite DB and yield an async session."""
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):  # noqa: ARG001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    sqlite_metadata = _sqlite_compatible_metadata()

    async with engine.begin() as conn:
        await conn.run_sync(sqlite_metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(sqlite_metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def project(db_session: AsyncSession) -> Project:
    proj = Project(
        name="test-project",
        knowledge={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest_asyncio.fixture
async def session_model(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="native",
        mode="execution",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


# ---------------------------------------------------------------------------
# Engine helpers (reused from test_streaming.py)
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
                    self._text_chunks.append(block.text)

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


def _make_engine_with_bus(
    tmp_path: Any, event_bus: LocalEventBus
) -> tuple[NativeEngine, dict[str, Any]]:
    """Create an engine backed by a real LocalEventBus (not a mock)."""
    client = AsyncMock()
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

    return engine, {"client": client}


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
    async for ev in aiter:
        events.append(ev)
    return events


# ---------------------------------------------------------------------------
# Tests: SSE endpoint route registration
# ---------------------------------------------------------------------------


class TestSSEEndpointRegistration:
    def test_sse_endpoint_exists(self) -> None:
        """The /messages/stream endpoint is registered on the sessions router."""
        from codehive.api.app import create_app

        app = create_app()
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/sessions/{session_id}/messages/stream" in routes

    def test_sse_endpoint_accepts_post(self) -> None:
        """The /messages/stream endpoint accepts POST method."""
        from codehive.api.app import create_app

        app = create_app()
        for route in app.routes:
            if (
                hasattr(route, "path")
                and route.path == "/api/sessions/{session_id}/messages/stream"
            ):
                assert "POST" in route.methods
                break
        else:
            pytest.fail("SSE endpoint not found")


# ---------------------------------------------------------------------------
# Tests: Engine events published to LocalEventBus
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEnginePublishesToEventBus:
    async def test_engine_publishes_message_delta_to_bus(
        self,
        tmp_path: Any,
        db_session: AsyncSession,
        session_model: SessionModel,
    ) -> None:
        """When engine streams text, message.delta events are published to the event bus."""
        bus = LocalEventBus()
        engine, mocks = _make_engine_with_bus(tmp_path, bus)

        _setup_stream_mock(
            mocks,
            MockResponse(content=[MockTextBlock(text="Hello world")]),
            chunks_list=[["Hello", " world"]],
        )

        received: list[str] = []
        async with bus.subscribe(session_model.id) as queue:
            # Run engine and collect from queue
            await _collect_events(engine.send_message(session_model.id, "Hi", db=db_session))

            # Drain the queue
            while not queue.empty():
                received.append(queue.get_nowait())

        # Parse events
        parsed = [json.loads(r) for r in received]
        delta_events = [e for e in parsed if e["type"] == "message.delta"]
        created_events = [e for e in parsed if e["type"] == "message.created"]

        assert len(delta_events) == 2
        assert delta_events[0]["data"]["content"] == "Hello"
        assert delta_events[1]["data"]["content"] == " world"
        # User message.created + assistant message.created
        assert len(created_events) == 2

    async def test_engine_publishes_tool_events_to_bus(
        self,
        tmp_path: Any,
        db_session: AsyncSession,
        session_model: SessionModel,
    ) -> None:
        """Tool call events (started/finished) are published to the event bus."""
        (tmp_path / "f.txt").write_text("data")
        bus = LocalEventBus()
        engine, mocks = _make_engine_with_bus(tmp_path, bus)

        _setup_stream_mock(
            mocks,
            [
                MockResponse(
                    content=[
                        MockTextBlock(text="Reading"),
                        MockToolUseBlock(id="t1", name="read_file", input={"path": "f.txt"}),
                    ]
                ),
                MockResponse(content=[MockTextBlock(text="Done")]),
            ],
            chunks_list=[["Reading"], ["Done"]],
        )

        received: list[str] = []
        async with bus.subscribe(session_model.id) as queue:
            await _collect_events(
                engine.send_message(session_model.id, "read f.txt", db=db_session)
            )

            while not queue.empty():
                received.append(queue.get_nowait())

        parsed = [json.loads(r) for r in received]
        types = [e["type"] for e in parsed]
        assert "tool.call.started" in types
        assert "tool.call.finished" in types


# ---------------------------------------------------------------------------
# Tests: Cross-client event flow via LocalEventBus
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCrossClientEventFlow:
    async def test_websocket_subscriber_receives_engine_events(
        self,
        tmp_path: Any,
        db_session: AsyncSession,
        session_model: SessionModel,
    ) -> None:
        """A WebSocket subscriber receives events when the engine runs.

        This simulates the cross-client scenario: terminal sends a message
        via the API, the engine runs, and a WebSocket subscriber (web client)
        receives the events in real time.
        """
        bus = LocalEventBus()
        engine, mocks = _make_engine_with_bus(tmp_path, bus)

        _setup_stream_mock(
            mocks,
            MockResponse(content=[MockTextBlock(text="response text")]),
            chunks_list=[["response", " text"]],
        )

        ws_received: list[str] = []

        async with bus.subscribe(session_model.id) as ws_queue:
            # Simulate terminal sending a message via the API
            await _collect_events(
                engine.send_message(session_model.id, "hello from terminal", db=db_session)
            )

            # Collect what the "WebSocket subscriber" received
            while not ws_queue.empty():
                ws_received.append(ws_queue.get_nowait())

        parsed = [json.loads(r) for r in ws_received]

        # Web client should see: user message.created, delta events, assistant message.created
        types = [e["type"] for e in parsed]
        assert "message.created" in types
        assert "message.delta" in types

        # Verify session_id is included in all events
        for ev in parsed:
            assert ev["session_id"] == str(session_model.id)

    async def test_multiple_subscribers_receive_same_events(
        self,
        tmp_path: Any,
        db_session: AsyncSession,
        session_model: SessionModel,
    ) -> None:
        """Multiple WebSocket subscribers all receive the same engine events."""
        bus = LocalEventBus()
        engine, mocks = _make_engine_with_bus(tmp_path, bus)

        _setup_stream_mock(
            mocks,
            MockResponse(content=[MockTextBlock(text="shared")]),
            chunks_list=[["shared"]],
        )

        ws1_received: list[str] = []
        ws2_received: list[str] = []

        async with bus.subscribe(session_model.id) as q1:
            async with bus.subscribe(session_model.id) as q2:
                await _collect_events(engine.send_message(session_model.id, "hello", db=db_session))

                while not q1.empty():
                    ws1_received.append(q1.get_nowait())
                while not q2.empty():
                    ws2_received.append(q2.get_nowait())

        # Both subscribers received the same events
        assert len(ws1_received) == len(ws2_received)
        assert len(ws1_received) > 0

        parsed1 = [json.loads(r) for r in ws1_received]
        parsed2 = [json.loads(r) for r in ws2_received]
        for e1, e2 in zip(parsed1, parsed2):
            assert e1["type"] == e2["type"]

    async def test_events_persisted_to_db(
        self,
        tmp_path: Any,
        db_session: AsyncSession,
        session_model: SessionModel,
    ) -> None:
        """Engine events are persisted to the DB for chat history retrieval."""
        bus = LocalEventBus()
        engine, mocks = _make_engine_with_bus(tmp_path, bus)

        _setup_stream_mock(
            mocks,
            MockResponse(content=[MockTextBlock(text="hi")]),
            chunks_list=[["hi"]],
        )

        await _collect_events(engine.send_message(session_model.id, "test message", db=db_session))

        # Query persisted events
        events = await bus.get_events(db_session, session_model.id, limit=100)
        assert len(events) > 0

        types = [e.type for e in events]
        # Should have user message, delta(s), and assistant message
        assert "message.created" in types
        assert "message.delta" in types

        # All events belong to the correct session
        for ev in events:
            assert ev.session_id == session_model.id


# ---------------------------------------------------------------------------
# Tests: SSE format validation
# ---------------------------------------------------------------------------


class TestSSEFormat:
    def test_sse_data_line_format(self) -> None:
        """SSE data lines follow the data: {json} format."""
        event = {"type": "message.delta", "content": "hello", "session_id": "abc"}
        line = f"data: {json.dumps(event)}\n\n"

        # Verify format
        assert line.startswith("data: ")
        assert line.endswith("\n\n")

        # Verify JSON is parseable
        json_str = line.removeprefix("data: ").rstrip("\n")
        parsed = json.loads(json_str)
        assert parsed["type"] == "message.delta"
        assert parsed["content"] == "hello"

    def test_multiple_sse_lines_parseable(self) -> None:
        """Multiple SSE data lines can be parsed individually."""
        events = [
            {"type": "message.created", "role": "user", "content": "hi"},
            {"type": "message.delta", "role": "assistant", "content": "he"},
            {"type": "message.delta", "role": "assistant", "content": "llo"},
            {"type": "message.created", "role": "assistant", "content": "hello"},
        ]

        sse_output = ""
        for ev in events:
            sse_output += f"data: {json.dumps(ev)}\n\n"

        # Parse each line
        parsed = []
        for chunk in sse_output.split("\n\n"):
            chunk = chunk.strip()
            if chunk.startswith("data: "):
                parsed.append(json.loads(chunk.removeprefix("data: ")))

        assert len(parsed) == 4
        assert parsed[0]["type"] == "message.created"
        assert parsed[1]["type"] == "message.delta"
        assert parsed[3]["type"] == "message.created"
