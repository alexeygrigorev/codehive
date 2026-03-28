"""Tests for session message persistence and GET /messages endpoint (issue #158)."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.usage import CHAT_EVENT_TYPES, persist_chat_event
from codehive.db.models import Base, Event, Project
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
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
async def session_obj(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="claude_code",
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
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/register",
            json={"email": "test@test.com", "username": "testuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit: persist_chat_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPersistChatEvent:
    async def test_persists_message_created(
        self, db_session: AsyncSession, session_obj: SessionModel
    ):
        """message.created events are persisted to the events table."""
        event_dict = {
            "type": "message.created",
            "role": "user",
            "content": "Hello world",
            "session_id": str(session_obj.id),
        }
        event_id = await persist_chat_event(db_session, session_obj.id, event_dict)
        assert event_id is not None

        db_event = await db_session.get(Event, event_id)
        assert db_event is not None
        assert db_event.type == "message.created"
        assert db_event.data["content"] == "Hello world"

    async def test_persists_tool_call_started(
        self, db_session: AsyncSession, session_obj: SessionModel
    ):
        """tool.call.started events are persisted."""
        event_dict = {
            "type": "tool.call.started",
            "call_id": "c1",
            "tool_name": "bash",
            "input": "ls -la",
        }
        event_id = await persist_chat_event(db_session, session_obj.id, event_dict)
        assert event_id is not None

        db_event = await db_session.get(Event, event_id)
        assert db_event is not None
        assert db_event.type == "tool.call.started"
        assert db_event.data["tool_name"] == "bash"

    async def test_persists_tool_call_finished(
        self, db_session: AsyncSession, session_obj: SessionModel
    ):
        """tool.call.finished events are persisted."""
        event_dict = {
            "type": "tool.call.finished",
            "call_id": "c1",
            "output": "file1.txt",
            "is_error": False,
        }
        event_id = await persist_chat_event(db_session, session_obj.id, event_dict)
        assert event_id is not None

        db_event = await db_session.get(Event, event_id)
        assert db_event is not None
        assert db_event.type == "tool.call.finished"

    async def test_ignores_non_chat_events(
        self, db_session: AsyncSession, session_obj: SessionModel
    ):
        """Non-chat events (e.g. rate_limit.updated) return None."""
        event_dict = {
            "type": "rate_limit.updated",
            "utilization": 0.5,
        }
        result = await persist_chat_event(db_session, session_obj.id, event_dict)
        assert result is None

    async def test_ignores_unknown_type(self, db_session: AsyncSession, session_obj: SessionModel):
        """Unknown event types return None."""
        event_dict = {"type": "some.unknown.event", "data": "foo"}
        result = await persist_chat_event(db_session, session_obj.id, event_dict)
        assert result is None

    async def test_all_chat_types_accepted(
        self, db_session: AsyncSession, session_obj: SessionModel
    ):
        """All CHAT_EVENT_TYPES are accepted by persist_chat_event."""
        for event_type in CHAT_EVENT_TYPES:
            event_dict = {"type": event_type, "content": "test"}
            result = await persist_chat_event(db_session, session_obj.id, event_dict)
            assert result is not None, f"{event_type} should be persisted"


# ---------------------------------------------------------------------------
# Integration: GET /api/sessions/{id}/messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetSessionMessages:
    async def test_returns_chat_events(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_obj: SessionModel,
    ):
        """GET /messages returns persisted chat events in chronological order."""
        # Insert 5 events of various chat types
        for i, etype in enumerate(
            [
                "message.created",
                "tool.call.started",
                "tool.call.finished",
                "message.created",
                "error",
            ]
        ):
            e = Event(
                session_id=session_obj.id,
                type=etype,
                data={"content": f"event-{i}"},
                created_at=datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc),
            )
            db_session.add(e)
        await db_session.commit()

        resp = await client.get(f"/api/sessions/{session_obj.id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        # Verify chronological order
        for i in range(len(data) - 1):
            assert data[i]["created_at"] <= data[i + 1]["created_at"]

    async def test_404_for_nonexistent_session(self, client: AsyncClient):
        """GET /messages returns 404 for non-existent session."""
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/messages")
        assert resp.status_code == 404

    async def test_filters_out_non_chat_events(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_obj: SessionModel,
    ):
        """GET /messages does not return non-chat events like rate_limit.updated."""
        # Insert a chat event and a non-chat event
        db_session.add(
            Event(
                session_id=session_obj.id,
                type="message.created",
                data={"role": "user", "content": "hi"},
                created_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            )
        )
        db_session.add(
            Event(
                session_id=session_obj.id,
                type="rate_limit.updated",
                data={"utilization": 0.5},
                created_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
            )
        )
        await db_session.commit()

        resp = await client.get(f"/api/sessions/{session_obj.id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["type"] == "message.created"

    async def test_large_history_not_capped_at_50(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_obj: SessionModel,
    ):
        """GET /messages returns more than 50 events (no hard cap at 50)."""
        for i in range(150):
            minute, second = divmod(i, 60)
            db_session.add(
                Event(
                    session_id=session_obj.id,
                    type="message.created",
                    data={"content": f"msg-{i}"},
                    created_at=datetime(2026, 1, 1, 0, minute, second, tzinfo=timezone.utc),
                )
            )
        await db_session.commit()

        resp = await client.get(f"/api/sessions/{session_obj.id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 150

    async def test_empty_session_returns_empty(
        self,
        client: AsyncClient,
        session_obj: SessionModel,
    ):
        """GET /messages returns empty list for session with no events."""
        resp = await client.get(f"/api/sessions/{session_obj.id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data == []
