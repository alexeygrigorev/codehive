"""Tests for LocalEventBus and create_event_bus factory."""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import JSON, MetaData, Table, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.core.events import (
    EventBus,
    LocalEventBus,
    SessionNotFoundError,
    create_event_bus,
)
from codehive.db.models import Base, Event, Project, Workspace
from codehive.db.models import Session as SessionModel

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
async def workspace(db_session: AsyncSession) -> Workspace:
    ws = Workspace(
        name="test-workspace",
        root_path="/tmp/test",
        settings={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    return ws


@pytest_asyncio.fixture
async def project(db_session: AsyncSession, workspace: Workspace) -> Project:
    proj = Project(
        workspace_id=workspace.id,
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


@pytest_asyncio.fixture
async def local_bus() -> LocalEventBus:
    return LocalEventBus()


# ---------------------------------------------------------------------------
# Unit tests: LocalEventBus.publish
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLocalEventBusPublish:
    async def test_publish_persists_to_db(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        local_bus: LocalEventBus,
    ):
        """Publish an event and verify it is persisted in the events table."""
        ev = await local_bus.publish(
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

        loaded = await db_session.get(Event, ev.id)
        assert loaded is not None
        assert loaded.type == "message.created"

    async def test_publish_broadcasts_to_subscriber(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        local_bus: LocalEventBus,
    ):
        """Subscribe to a session, publish an event, verify subscriber receives it."""
        async with local_bus.subscribe(session_model.id) as queue:
            await local_bus.publish(
                db_session,
                session_model.id,
                "task.started",
                {"task": "build"},
            )
            msg = queue.get_nowait()
            parsed = json.loads(msg)
            assert parsed["type"] == "task.started"
            assert parsed["data"] == {"task": "build"}
            assert parsed["session_id"] == str(session_model.id)

    async def test_two_subscribers_both_receive(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        local_bus: LocalEventBus,
    ):
        """Two subscribers to the same session both receive the same event."""
        async with local_bus.subscribe(session_model.id) as q1:
            async with local_bus.subscribe(session_model.id) as q2:
                await local_bus.publish(
                    db_session,
                    session_model.id,
                    "file.changed",
                    {"path": "/foo.py"},
                )
                msg1 = json.loads(q1.get_nowait())
                msg2 = json.loads(q2.get_nowait())
                assert msg1["type"] == "file.changed"
                assert msg2["type"] == "file.changed"
                assert msg1 == msg2

    async def test_unsubscribe_stops_delivery(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        local_bus: LocalEventBus,
    ):
        """After unsubscribing, the queue does NOT receive new events."""
        async with local_bus.subscribe(session_model.id) as queue:
            pass  # exiting the context manager unsubscribes

        # Publish after unsubscribe
        await local_bus.publish(
            db_session,
            session_model.id,
            "task.completed",
            {"task": "build"},
        )
        assert queue.empty()

    async def test_cross_session_isolation(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        local_bus: LocalEventBus,
        project: Project,
    ):
        """Publish to session A, subscriber to session B does NOT receive it."""
        # Create a second session
        s2 = SessionModel(
            project_id=project.id,
            name="other-session",
            engine="native",
            mode="execution",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(s2)
        await db_session.commit()
        await db_session.refresh(s2)

        async with local_bus.subscribe(s2.id) as queue_b:
            await local_bus.publish(
                db_session,
                session_model.id,
                "task.started",
                {"task": "a"},
            )
            assert queue_b.empty()

    async def test_subscribe_cleans_up_empty_lists(
        self,
        local_bus: LocalEventBus,
    ):
        """After all subscribers leave, the session key is removed (no memory leak)."""
        sid = uuid.uuid4()
        async with local_bus.subscribe(sid):
            assert sid in local_bus._subscribers

        # After context exit, the key should be gone
        assert sid not in local_bus._subscribers


# ---------------------------------------------------------------------------
# Unit tests: LocalEventBus.get_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLocalEventBusGetEvents:
    async def test_get_events_nonexistent_session(
        self,
        db_session: AsyncSession,
        local_bus: LocalEventBus,
    ):
        with pytest.raises(SessionNotFoundError):
            await local_bus.get_events(db_session, uuid.uuid4())

    async def test_get_events_returns_published(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        local_bus: LocalEventBus,
    ):
        await local_bus.publish(db_session, session_model.id, "a", {"n": 1})
        await local_bus.publish(db_session, session_model.id, "b", {"n": 2})

        events = await local_bus.get_events(db_session, session_model.id, limit=100)
        assert len(events) == 2
        assert events[0].type == "a"
        assert events[1].type == "b"


# ---------------------------------------------------------------------------
# Unit tests: create_event_bus factory
# ---------------------------------------------------------------------------


class TestCreateEventBus:
    def test_empty_string_returns_local(self):
        bus = create_event_bus("")
        assert isinstance(bus, LocalEventBus)

    def test_no_args_returns_local(self):
        bus = create_event_bus()
        assert isinstance(bus, LocalEventBus)

    def test_redis_url_returns_event_bus(self):
        bus = create_event_bus("redis://localhost:6379")
        assert isinstance(bus, EventBus)
