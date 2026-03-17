"""Tests for ReplayService and session replay REST endpoint."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.events import SessionNotFoundError
from codehive.core.replay import ReplayService, SessionNotReplayableError
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
async def completed_session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="completed-session",
        engine="native",
        mode="execution",
        status="completed",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def failed_session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="failed-session",
        engine="native",
        mode="execution",
        status="failed",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def in_progress_session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="in-progress-session",
        engine="native",
        mode="execution",
        status="executing",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def replay_service() -> ReplayService:
    return ReplayService()


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
# Helper to seed events
# ---------------------------------------------------------------------------


async def _seed_events(
    db: AsyncSession,
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
# Unit tests: ReplayService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestReplayServiceUnit:
    async def test_build_replay_mixed_event_types(
        self,
        db_session: AsyncSession,
        completed_session: SessionModel,
        replay_service: ReplayService,
    ):
        """Build replay with mixed event types; verify ordered by timestamp and indexed."""
        await _seed_events(
            db_session,
            completed_session.id,
            [
                ("message.created", {"role": "user", "content": "hello"}),
                ("tool.call.started", {"tool": "edit_file"}),
                ("tool.call.finished", {"tool": "edit_file", "output": "ok"}),
                ("file.changed", {"path": "main.py", "action": "edit"}),
            ],
        )

        result = await replay_service.build_replay(db_session, completed_session.id)

        assert result.total_steps == 4
        assert len(result.steps) == 4
        assert result.session_id == completed_session.id
        assert result.session_status == "completed"

        # Verify ordering and indexing
        for i, step in enumerate(result.steps):
            assert step["index"] == i

        # Verify step_type mapping
        assert result.steps[0]["step_type"] == "message"
        assert result.steps[1]["step_type"] == "tool_call_start"
        assert result.steps[2]["step_type"] == "tool_call_finish"
        assert result.steps[3]["step_type"] == "file_change"

    async def test_build_replay_empty_session(
        self,
        db_session: AsyncSession,
        completed_session: SessionModel,
        replay_service: ReplayService,
    ):
        """Build replay for session with zero events returns empty list."""
        result = await replay_service.build_replay(db_session, completed_session.id)

        assert result.total_steps == 0
        assert result.steps == []

    async def test_build_replay_pagination(
        self,
        db_session: AsyncSession,
        completed_session: SessionModel,
        replay_service: ReplayService,
    ):
        """Verify pagination: offset=2, limit=2 on 5 events returns indices 2-3."""
        await _seed_events(
            db_session,
            completed_session.id,
            [
                ("message.created", {"idx": 0}),
                ("tool.call.started", {"idx": 1}),
                ("tool.call.finished", {"idx": 2}),
                ("file.changed", {"idx": 3}),
                ("task.completed", {"idx": 4}),
            ],
        )

        result = await replay_service.build_replay(
            db_session, completed_session.id, offset=2, limit=2
        )

        assert result.total_steps == 5
        assert len(result.steps) == 2
        assert result.steps[0]["index"] == 2
        assert result.steps[1]["index"] == 3

    async def test_step_type_mapping(
        self,
        db_session: AsyncSession,
        completed_session: SessionModel,
        replay_service: ReplayService,
    ):
        """Verify step_type mapping for all known event types."""
        await _seed_events(
            db_session,
            completed_session.id,
            [
                ("message.created", {}),
                ("tool.call.started", {}),
                ("tool.call.finished", {}),
                ("file.changed", {}),
                ("task.started", {}),
                ("task.completed", {}),
                ("session.status_changed", {}),
                ("unknown.event.type", {}),
            ],
        )

        result = await replay_service.build_replay(db_session, completed_session.id, limit=200)

        expected_types = [
            "message",
            "tool_call_start",
            "tool_call_finish",
            "file_change",
            "task_started",
            "task_completed",
            "session_status_change",
            "unknown.event.type",  # falls back to original event type
        ]

        for step, expected in zip(result.steps, expected_types):
            assert step["step_type"] == expected

    async def test_nonexistent_session_raises(
        self,
        db_session: AsyncSession,
        replay_service: ReplayService,
    ):
        """Build replay for nonexistent session raises SessionNotFoundError."""
        with pytest.raises(SessionNotFoundError):
            await replay_service.build_replay(db_session, uuid.uuid4())

    async def test_in_progress_session_raises(
        self,
        db_session: AsyncSession,
        in_progress_session: SessionModel,
        replay_service: ReplayService,
    ):
        """Build replay for in-progress session raises SessionNotReplayableError."""
        with pytest.raises(SessionNotReplayableError):
            await replay_service.build_replay(db_session, in_progress_session.id)

    async def test_failed_session_is_replayable(
        self,
        db_session: AsyncSession,
        failed_session: SessionModel,
        replay_service: ReplayService,
    ):
        """Failed sessions should be replayable."""
        result = await replay_service.build_replay(db_session, failed_session.id)
        assert result.session_status == "failed"
        assert result.total_steps == 0


# ---------------------------------------------------------------------------
# Integration tests: Replay REST endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestReplayRESTEndpoint:
    async def test_replay_completed_session(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        completed_session: SessionModel,
    ):
        """GET /api/sessions/{id}/replay returns 200 with correct schema."""
        await _seed_events(
            db_session,
            completed_session.id,
            [
                ("message.created", {"role": "user"}),
                ("tool.call.started", {"tool": "edit_file"}),
                ("tool.call.finished", {"tool": "edit_file"}),
            ],
        )

        resp = await client.get(f"/api/sessions/{completed_session.id}/replay")
        assert resp.status_code == 200
        data = resp.json()

        assert data["session_id"] == str(completed_session.id)
        assert data["session_status"] == "completed"
        assert data["total_steps"] == 3
        assert len(data["steps"]) == 3

        for step in data["steps"]:
            assert "index" in step
            assert "timestamp" in step
            assert "step_type" in step
            assert "data" in step

    async def test_replay_nonexistent_session_404(self, client: AsyncClient):
        """GET /api/sessions/{id}/replay for nonexistent session returns 404."""
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/replay")
        assert resp.status_code == 404

    async def test_replay_in_progress_session_409(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        in_progress_session: SessionModel,
    ):
        """GET /api/sessions/{id}/replay for in-progress session returns 409."""
        resp = await client.get(f"/api/sessions/{in_progress_session.id}/replay")
        assert resp.status_code == 409
        data = resp.json()
        assert "detail" in data

    async def test_replay_pagination(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        completed_session: SessionModel,
    ):
        """GET /api/sessions/{id}/replay?limit=2&offset=0 returns exactly 2 steps."""
        await _seed_events(
            db_session,
            completed_session.id,
            [
                ("message.created", {}),
                ("tool.call.started", {}),
                ("tool.call.finished", {}),
                ("file.changed", {}),
            ],
        )

        resp = await client.get(f"/api/sessions/{completed_session.id}/replay?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_steps"] == 4
        assert len(data["steps"]) == 2
        assert data["steps"][0]["index"] == 0
        assert data["steps"][1]["index"] == 1

    async def test_replay_response_schema(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        completed_session: SessionModel,
    ):
        """Verify the response schema matches ReplayResponse."""
        await _seed_events(
            db_session,
            completed_session.id,
            [("message.created", {"role": "assistant", "content": "hi"})],
        )

        resp = await client.get(f"/api/sessions/{completed_session.id}/replay")
        assert resp.status_code == 200
        data = resp.json()

        # Top-level keys
        assert set(data.keys()) == {"session_id", "session_status", "total_steps", "steps"}
        # Step keys
        step = data["steps"][0]
        assert set(step.keys()) == {"index", "timestamp", "step_type", "data"}
