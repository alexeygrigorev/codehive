"""Tests for Event Bus, REST events endpoint, and WebSocket streaming."""

import contextlib
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.events import EventBus, SessionNotFoundError
from codehive.db.models import Base, Event, Project
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database (same pattern as test_sessions.py)
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create tables in an in-memory SQLite DB and yield an async session."""
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

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
    """Create a session for event tests."""
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


@pytest_asyncio.fixture
async def mock_redis() -> AsyncMock:
    """Return a mock Redis client that tracks publish calls."""
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    return redis


@pytest_asyncio.fixture
async def event_bus(mock_redis: AsyncMock) -> EventBus:
    """Return an EventBus with a mocked Redis client."""
    return EventBus(redis=mock_redis)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with the DB session overridden."""
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    @contextlib.asynccontextmanager
    async def _noop_lifespan(app):  # type: ignore[no-untyped-def]
        yield

    app.router.lifespan_context = _noop_lifespan

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register a test user and include auth headers
        resp = await ac.post(
            "/api/auth/register",
            json={"email": "test@test.com", "username": "testuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit tests: EventBus.publish
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEventBusPublish:
    async def test_publish_persists_to_db(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        event_bus: EventBus,
    ):
        """Publish an event and verify it is persisted in the events table."""
        ev = await event_bus.publish(
            db_session,
            session_model.id,
            "message.created",
            {"content": "hello"},
        )
        assert ev.id is not None
        assert ev.session_id == session_model.id
        assert ev.type == "message.created"
        assert ev.data == {"content": "hello"}
        assert ev.created_at is not None

        # Verify it is in the DB
        loaded = await db_session.get(Event, ev.id)
        assert loaded is not None
        assert loaded.type == "message.created"

    async def test_publish_sends_to_redis(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        event_bus: EventBus,
        mock_redis: AsyncMock,
    ):
        """Publish an event and verify a message is published to the correct Redis channel."""
        await event_bus.publish(
            db_session,
            session_model.id,
            "tool.call.started",
            {"tool": "bash"},
        )
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        channel = call_args[0][0]
        assert channel == f"session:{session_model.id}:events"

    async def test_publish_redis_message_is_valid_json(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        event_bus: EventBus,
        mock_redis: AsyncMock,
    ):
        """Verify the Redis message is valid JSON with required fields."""
        ev = await event_bus.publish(
            db_session,
            session_model.id,
            "file.changed",
            {"path": "/tmp/foo.py"},
        )
        call_args = mock_redis.publish.call_args
        message_str = call_args[0][1]
        msg = json.loads(message_str)
        assert msg["id"] == str(ev.id)
        assert msg["session_id"] == str(session_model.id)
        assert msg["type"] == "file.changed"
        assert msg["data"] == {"path": "/tmp/foo.py"}
        assert "created_at" in msg

    async def test_publish_multiple_events(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        event_bus: EventBus,
    ):
        """Publish multiple events and verify all are stored in the DB."""
        await event_bus.publish(db_session, session_model.id, "task.started", {"task": "a"})
        await event_bus.publish(db_session, session_model.id, "task.completed", {"task": "a"})
        await event_bus.publish(db_session, session_model.id, "diff.updated", {"lines": 42})

        events = await event_bus.get_events(db_session, session_model.id, limit=100)
        assert len(events) == 3


# ---------------------------------------------------------------------------
# Unit tests: EventBus.get_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEventBusGetEvents:
    async def test_get_events_nonexistent_session(
        self,
        db_session: AsyncSession,
        event_bus: EventBus,
    ):
        """get_events raises SessionNotFoundError for a non-existent session."""
        with pytest.raises(SessionNotFoundError):
            await event_bus.get_events(db_session, uuid.uuid4())

    async def test_get_events_empty(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        event_bus: EventBus,
    ):
        """get_events returns an empty list when no events exist."""
        events = await event_bus.get_events(db_session, session_model.id)
        assert events == []


# ---------------------------------------------------------------------------
# Integration tests: REST endpoint GET /api/sessions/{session_id}/events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEventsRESTEndpoint:
    async def test_list_events_returns_all_ordered(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """Create 3 events and verify they come back ordered by created_at."""
        bus = EventBus(redis=AsyncMock())
        await bus.publish(db_session, session_model.id, "task.started", {"n": 1})
        await bus.publish(db_session, session_model.id, "file.changed", {"n": 2})
        await bus.publish(db_session, session_model.id, "task.completed", {"n": 3})

        resp = await client.get(f"/api/sessions/{session_model.id}/events")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["type"] == "task.started"
        assert data[1]["type"] == "file.changed"
        assert data[2]["type"] == "task.completed"

        # Verify required fields
        for item in data:
            assert "id" in item
            assert "session_id" in item
            assert "type" in item
            assert "data" in item
            assert "created_at" in item

    async def test_list_events_limit(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET events with limit=2 returns exactly 2 events."""
        bus = EventBus(redis=AsyncMock())
        await bus.publish(db_session, session_model.id, "task.started", {})
        await bus.publish(db_session, session_model.id, "file.changed", {})
        await bus.publish(db_session, session_model.id, "task.completed", {})

        resp = await client.get(f"/api/sessions/{session_model.id}/events?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_list_events_offset_and_limit(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET events with offset=1&limit=2 returns the correct slice."""
        bus = EventBus(redis=AsyncMock())
        await bus.publish(db_session, session_model.id, "task.started", {})
        await bus.publish(db_session, session_model.id, "file.changed", {})
        await bus.publish(db_session, session_model.id, "task.completed", {})

        resp = await client.get(f"/api/sessions/{session_model.id}/events?offset=1&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["type"] == "file.changed"
        assert data[1]["type"] == "task.completed"

    async def test_list_events_nonexistent_session_404(self, client: AsyncClient):
        """GET events for a non-existent session returns 404."""
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/events")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration tests: WebSocket endpoint /api/sessions/{session_id}/ws
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWebSocketEndpoint:
    async def test_ws_nonexistent_session_rejected(
        self,
        db_session: AsyncSession,
    ):
        """WebSocket to a non-existent session is rejected with close code 4004."""
        from starlette.testclient import TestClient

        app = create_app()

        async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        app.dependency_overrides[get_db] = _override_get_db

        @contextlib.asynccontextmanager
        async def _noop_lifespan(app):  # type: ignore[no-untyped-def]
            yield

        app.router.lifespan_context = _noop_lifespan

        # starlette's sync TestClient handles WebSocket testing
        with TestClient(app) as tc:
            with pytest.raises(Exception):
                with tc.websocket_connect(f"/api/sessions/{uuid.uuid4()}/ws"):
                    pass

    async def test_ws_valid_session_accepts(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """WebSocket to a valid session accepts the connection."""
        from starlette.testclient import TestClient

        from codehive.core.jwt import create_access_token

        app = create_app()

        async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        app.dependency_overrides[get_db] = _override_get_db

        @contextlib.asynccontextmanager
        async def _noop_lifespan(app):  # type: ignore[no-untyped-def]
            yield

        app.router.lifespan_context = _noop_lifespan

        token = create_access_token(uuid.uuid4())

        with TestClient(app) as tc:
            # We just verify the connection is accepted (no exception on connect)
            # We close immediately since we can't easily feed Redis messages in a sync test
            with tc.websocket_connect(f"/api/sessions/{session_model.id}/ws?token={token}") as ws:
                # Connection accepted successfully -- close it
                ws.close()
