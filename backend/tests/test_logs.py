"""Tests for LogService, log REST endpoints, and engine event enrichment."""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.events import EventBus, SessionNotFoundError
from codehive.core.logs import LogService
from codehive.db.models import Base, Event, Project, Workspace
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database
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
async def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    return redis


@pytest_asyncio.fixture
async def event_bus(mock_redis: AsyncMock) -> EventBus:
    return EventBus(redis=mock_redis)


@pytest_asyncio.fixture
async def log_service() -> LogService:
    return LogService()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

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
# Helper to seed events with specific timestamps
# ---------------------------------------------------------------------------


async def _seed_events(
    db: AsyncSession,
    bus: EventBus,
    session_id: uuid.UUID,
    events: list[tuple[str, dict]],
    *,
    base_time: datetime | None = None,
) -> list[Event]:
    """Seed events with incrementing timestamps."""
    if base_time is None:
        base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    created = []
    for i, (etype, data) in enumerate(events):
        ev = Event(
            session_id=session_id,
            type=etype,
            data=data,
            created_at=base_time + timedelta(seconds=i),
        )
        db.add(ev)
        created.append(ev)
    await db.commit()
    for ev in created:
        await db.refresh(ev)
    return created


# ---------------------------------------------------------------------------
# Unit tests: LogService query logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLogServiceQuery:
    async def test_query_no_filters(
        self, db_session: AsyncSession, session_model: SessionModel, log_service: LogService
    ):
        """Query with no filters returns all events ordered by created_at."""
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [
                ("message.created", {"role": "user"}),
                ("tool.call.started", {"tool": "edit_file"}),
                ("tool.call.finished", {"tool": "edit_file"}),
            ],
        )
        result = await log_service.query(db_session, session_model.id)
        assert len(result.items) == 3
        assert result.total == 3
        assert result.items[0].type == "message.created"
        assert result.items[1].type == "tool.call.started"
        assert result.items[2].type == "tool.call.finished"

    async def test_query_single_type_filter(
        self, db_session: AsyncSession, session_model: SessionModel, log_service: LogService
    ):
        """Query with types=['message.created'] returns only message events."""
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [
                ("message.created", {"role": "user"}),
                ("tool.call.started", {"tool": "edit_file"}),
                ("message.created", {"role": "assistant"}),
            ],
        )
        result = await log_service.query(db_session, session_model.id, types=["message.created"])
        assert len(result.items) == 2
        assert result.total == 2
        assert all(e.type == "message.created" for e in result.items)

    async def test_query_multiple_type_filter(
        self, db_session: AsyncSession, session_model: SessionModel, log_service: LogService
    ):
        """Query with multiple types returns the union of matching events."""
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [
                ("message.created", {}),
                ("tool.call.started", {}),
                ("tool.call.finished", {}),
                ("file.changed", {}),
            ],
        )
        result = await log_service.query(
            db_session,
            session_model.id,
            types=["tool.call.started", "tool.call.finished"],
        )
        assert len(result.items) == 2
        assert result.total == 2
        types = {e.type for e in result.items}
        assert types == {"tool.call.started", "tool.call.finished"}

    async def test_query_after_filter(
        self, db_session: AsyncSession, session_model: SessionModel, log_service: LogService
    ):
        """Query with after datetime returns only events created after that time."""
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [("e1", {}), ("e2", {}), ("e3", {})],
            base_time=base,
        )
        # after base+0.5s should exclude the first event
        result = await log_service.query(
            db_session, session_model.id, after=base + timedelta(seconds=0, microseconds=500000)
        )
        assert len(result.items) == 2
        assert result.total == 2

    async def test_query_before_filter(
        self, db_session: AsyncSession, session_model: SessionModel, log_service: LogService
    ):
        """Query with before datetime returns only events created before that time."""
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [("e1", {}), ("e2", {}), ("e3", {})],
            base_time=base,
        )
        # before base+1.5s should include first two events
        result = await log_service.query(
            db_session,
            session_model.id,
            before=base + timedelta(seconds=1, microseconds=500000),
        )
        assert len(result.items) == 2
        assert result.total == 2

    async def test_query_after_and_before(
        self, db_session: AsyncSession, session_model: SessionModel, log_service: LogService
    ):
        """Query with both after and before returns events in that window."""
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [("e1", {}), ("e2", {}), ("e3", {}), ("e4", {})],
            base_time=base,
        )
        result = await log_service.query(
            db_session,
            session_model.id,
            after=base + timedelta(seconds=0, microseconds=500000),
            before=base + timedelta(seconds=2, microseconds=500000),
        )
        assert len(result.items) == 2
        assert result.total == 2

    async def test_query_limit(
        self, db_session: AsyncSession, session_model: SessionModel, log_service: LogService
    ):
        """Query with limit=2 returns at most 2 items; total reflects full count."""
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [("e1", {}), ("e2", {}), ("e3", {})],
        )
        result = await log_service.query(db_session, session_model.id, limit=2)
        assert len(result.items) == 2
        assert result.total == 3

    async def test_query_offset(
        self, db_session: AsyncSession, session_model: SessionModel, log_service: LogService
    ):
        """Query with offset=1, limit=2 skips the first event."""
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [("e1", {}), ("e2", {}), ("e3", {})],
        )
        result = await log_service.query(db_session, session_model.id, offset=1, limit=2)
        assert len(result.items) == 2
        assert result.items[0].type == "e2"
        assert result.items[1].type == "e3"
        assert result.total == 3

    async def test_query_nonexistent_session(
        self, db_session: AsyncSession, log_service: LogService
    ):
        """Query for a non-existent session raises SessionNotFoundError."""
        with pytest.raises(SessionNotFoundError):
            await log_service.query(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Unit tests: Engine event enrichment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEngineEventEnrichment:
    async def test_edit_file_emits_file_changed(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        event_bus: EventBus,
    ):
        """edit_file tool call emits a file.changed event."""
        from codehive.engine.native import NativeEngine

        mock_file_ops = AsyncMock()
        mock_file_ops.edit_file = AsyncMock(return_value="File edited successfully")
        mock_file_ops._root = MagicMock()
        mock_shell = AsyncMock()
        mock_git = AsyncMock()
        mock_git.current_sha = AsyncMock(return_value="abc123")
        mock_git.commit = AsyncMock(return_value="abc123")
        mock_diff = MagicMock()

        engine = NativeEngine(
            client=AsyncMock(),
            event_bus=event_bus,
            file_ops=mock_file_ops,
            shell_runner=mock_shell,
            git_ops=mock_git,
            diff_service=mock_diff,
        )

        result = await engine._execute_tool_direct(
            "edit_file",
            {"path": "src/main.py", "old_text": "foo", "new_text": "bar"},
            session_id=session_model.id,
            db=db_session,
        )

        assert result["content"] == "File edited successfully"

        # Verify a file.changed event was published
        from sqlalchemy import select

        stmt = select(Event).where(
            Event.session_id == session_model.id,
            Event.type == "file.changed",
        )
        events = (await db_session.execute(stmt)).scalars().all()
        assert len(events) == 1
        assert events[0].data["path"] == "src/main.py"
        assert events[0].data["action"] == "edit"

    async def test_run_shell_emits_terminal_output(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        event_bus: EventBus,
    ):
        """run_shell tool call emits a terminal.output event."""
        from codehive.engine.native import NativeEngine

        mock_file_ops = AsyncMock()
        mock_file_ops._root = MagicMock()
        mock_file_ops._root.__truediv__ = MagicMock(
            return_value=MagicMock(is_absolute=MagicMock(return_value=False))
        )

        shell_result = MagicMock()
        shell_result.stdout = "hello world"
        shell_result.stderr = ""
        shell_result.exit_code = 0
        shell_result.timed_out = False

        mock_shell = AsyncMock()
        mock_shell.run = AsyncMock(return_value=shell_result)
        mock_git = AsyncMock()
        mock_git.current_sha = AsyncMock(return_value="abc123")
        mock_git.commit = AsyncMock(return_value="abc123")
        mock_diff = MagicMock()

        engine = NativeEngine(
            client=AsyncMock(),
            event_bus=event_bus,
            file_ops=mock_file_ops,
            shell_runner=mock_shell,
            git_ops=mock_git,
            diff_service=mock_diff,
        )

        result = await engine._execute_tool_direct(
            "run_shell",
            {"command": "echo hello"},
            session_id=session_model.id,
            db=db_session,
        )

        parsed = json.loads(result["content"])
        assert parsed["exit_code"] == 0

        # Verify a terminal.output event was published
        from sqlalchemy import select

        stmt = select(Event).where(
            Event.session_id == session_model.id,
            Event.type == "terminal.output",
        )
        events = (await db_session.execute(stmt)).scalars().all()
        assert len(events) == 1
        assert events[0].data["command"] == "echo hello"
        assert events[0].data["exit_code"] == 0
        assert events[0].data["stdout"] == "hello world"
        assert events[0].data["stderr"] == ""


# ---------------------------------------------------------------------------
# Integration tests: REST log query endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLogsRESTEndpoint:
    async def test_query_returns_paginated_response(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET /api/sessions/{id}/logs returns paginated log entries."""
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [
                ("message.created", {"role": "user"}),
                ("tool.call.started", {"tool": "edit_file"}),
                ("tool.call.finished", {"tool": "edit_file"}),
            ],
        )

        resp = await client.get(f"/api/sessions/{session_model.id}/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["limit"] == 50
        assert data["offset"] == 0
        assert len(data["items"]) == 3

        for item in data["items"]:
            assert "id" in item
            assert "session_id" in item
            assert "type" in item
            assert "data" in item
            assert "created_at" in item

    async def test_query_filter_by_single_type(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET /api/sessions/{id}/logs?type=message.created filters by type."""
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [
                ("message.created", {}),
                ("tool.call.started", {}),
                ("message.created", {}),
            ],
        )

        resp = await client.get(f"/api/sessions/{session_model.id}/logs?type=message.created")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert all(i["type"] == "message.created" for i in data["items"])

    async def test_query_filter_by_multiple_types(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET /api/sessions/{id}/logs?type=a,b filters by multiple types."""
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [
                ("message.created", {}),
                ("tool.call.started", {}),
                ("tool.call.finished", {}),
                ("file.changed", {}),
            ],
        )

        resp = await client.get(
            f"/api/sessions/{session_model.id}/logs?type=tool.call.started,tool.call.finished"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_query_filter_by_time_range(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET /api/sessions/{id}/logs?after=...&before=... filters by time range."""
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [("e1", {}), ("e2", {}), ("e3", {}), ("e4", {})],
            base_time=base,
        )

        after_dt = base + timedelta(seconds=0, microseconds=500000)
        before_dt = base + timedelta(seconds=2, microseconds=500000)

        resp = await client.get(
            f"/api/sessions/{session_model.id}/logs",
            params={"after": after_dt.isoformat(), "before": before_dt.isoformat()},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_query_nonexistent_session_404(self, client: AsyncClient):
        """GET /api/sessions/{id}/logs for non-existent session returns 404."""
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/logs")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration tests: REST log export endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLogsExportEndpoint:
    async def test_export_returns_all_events(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET /api/sessions/{id}/logs/export returns all events with export schema."""
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [
                ("message.created", {}),
                ("tool.call.started", {}),
                ("tool.call.finished", {}),
            ],
        )

        resp = await client.get(f"/api/sessions/{session_model.id}/logs/export")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == str(session_model.id)
        assert "exported_at" in data
        assert data["event_count"] == 3
        assert len(data["events"]) == 3

    async def test_export_filtered_by_type(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET /api/sessions/{id}/logs/export?type=tool.call.started exports filtered subset."""
        await _seed_events(
            db_session,
            None,
            session_model.id,
            [
                ("message.created", {}),
                ("tool.call.started", {}),
                ("tool.call.finished", {}),
            ],
        )

        resp = await client.get(
            f"/api/sessions/{session_model.id}/logs/export?type=tool.call.started"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_count"] == 1
        assert len(data["events"]) == 1
        assert data["events"][0]["type"] == "tool.call.started"

    async def test_export_nonexistent_session_404(self, client: AsyncClient):
        """GET /api/sessions/{id}/logs/export for non-existent session returns 404."""
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/logs/export")
        assert resp.status_code == 404
