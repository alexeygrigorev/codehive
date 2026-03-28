"""Tests for pipeline state machine and API endpoints."""

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
from codehive.core.task_queue import (
    InvalidPipelineTransitionError,
    TaskNotFoundError,
    create_task,
    get_pipeline_log,
    pipeline_transition,
)
from codehive.db.models import Base, Project
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
async def session(db_session: AsyncSession, project: Project) -> SessionModel:
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
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/register",
            json={"email": "pipe@test.com", "username": "pipeuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit tests: Pipeline state machine logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPipelineStateMachine:
    """Unit tests for pipeline_transition()."""

    async def test_backlog_to_grooming(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        result = await pipeline_transition(db_session, task.id, "grooming")
        assert result.pipeline_status == "grooming"

    async def test_grooming_to_groomed(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await pipeline_transition(db_session, task.id, "grooming")
        result = await pipeline_transition(db_session, task.id, "groomed")
        assert result.pipeline_status == "groomed"

    async def test_groomed_to_implementing(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await pipeline_transition(db_session, task.id, "grooming")
        await pipeline_transition(db_session, task.id, "groomed")
        result = await pipeline_transition(db_session, task.id, "implementing")
        assert result.pipeline_status == "implementing"

    async def test_implementing_to_testing(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await pipeline_transition(db_session, task.id, "grooming")
        await pipeline_transition(db_session, task.id, "groomed")
        await pipeline_transition(db_session, task.id, "implementing")
        result = await pipeline_transition(db_session, task.id, "testing")
        assert result.pipeline_status == "testing"

    async def test_testing_to_accepting(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        for s in ["grooming", "groomed", "implementing", "testing"]:
            await pipeline_transition(db_session, task.id, s)
        result = await pipeline_transition(db_session, task.id, "accepting")
        assert result.pipeline_status == "accepting"

    async def test_testing_to_implementing_qa_reject(
        self, db_session: AsyncSession, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        for s in ["grooming", "groomed", "implementing", "testing"]:
            await pipeline_transition(db_session, task.id, s)
        result = await pipeline_transition(db_session, task.id, "implementing")
        assert result.pipeline_status == "implementing"

    async def test_accepting_to_done(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        for s in ["grooming", "groomed", "implementing", "testing", "accepting"]:
            await pipeline_transition(db_session, task.id, s)
        result = await pipeline_transition(db_session, task.id, "done")
        assert result.pipeline_status == "done"

    async def test_accepting_to_implementing_pm_reject(
        self, db_session: AsyncSession, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        for s in ["grooming", "groomed", "implementing", "testing", "accepting"]:
            await pipeline_transition(db_session, task.id, s)
        result = await pipeline_transition(db_session, task.id, "implementing")
        assert result.pipeline_status == "implementing"

    async def test_backlog_to_implementing_fails(
        self, db_session: AsyncSession, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        with pytest.raises(InvalidPipelineTransitionError, match="backlog.*implementing"):
            await pipeline_transition(db_session, task.id, "implementing")

    async def test_backlog_to_done_fails(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        with pytest.raises(InvalidPipelineTransitionError):
            await pipeline_transition(db_session, task.id, "done")

    async def test_done_is_terminal(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        for s in ["grooming", "groomed", "implementing", "testing", "accepting", "done"]:
            await pipeline_transition(db_session, task.id, s)
        with pytest.raises(InvalidPipelineTransitionError, match="terminal"):
            await pipeline_transition(db_session, task.id, "backlog")

    async def test_groomed_to_grooming_fails(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await pipeline_transition(db_session, task.id, "grooming")
        await pipeline_transition(db_session, task.id, "groomed")
        with pytest.raises(InvalidPipelineTransitionError):
            await pipeline_transition(db_session, task.id, "grooming")

    async def test_transition_creates_log_entry(
        self, db_session: AsyncSession, session: SessionModel
    ):
        task = await create_task(db_session, session_id=session.id, title="t")
        await pipeline_transition(db_session, task.id, "grooming", actor="pm-agent")
        logs = await get_pipeline_log(db_session, task.id)
        assert len(logs) == 1
        assert logs[0].from_status == "backlog"
        assert logs[0].to_status == "grooming"
        assert logs[0].actor == "pm-agent"
        assert logs[0].created_at is not None

    async def test_log_records_null_actor(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await pipeline_transition(db_session, task.id, "grooming")
        logs = await get_pipeline_log(db_session, task.id)
        assert logs[0].actor is None

    async def test_transition_nonexistent_task(self, db_session: AsyncSession):
        with pytest.raises(TaskNotFoundError):
            await pipeline_transition(db_session, uuid.uuid4(), "grooming")

    async def test_get_pipeline_log_nonexistent_task(self, db_session: AsyncSession):
        with pytest.raises(TaskNotFoundError):
            await get_pipeline_log(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Integration tests: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPipelineTransitionEndpoint:
    async def _create_task(self, client: AsyncClient, session: SessionModel) -> str:
        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "pipeline task"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_valid_transition_200(self, client: AsyncClient, session: SessionModel):
        task_id = await self._create_task(client, session)
        resp = await client.post(
            f"/api/tasks/{task_id}/pipeline-transition",
            json={"status": "grooming", "actor": "pm-session-abc"},
        )
        assert resp.status_code == 200
        assert resp.json()["pipeline_status"] == "grooming"

    async def test_invalid_transition_409(self, client: AsyncClient, session: SessionModel):
        task_id = await self._create_task(client, session)
        resp = await client.post(
            f"/api/tasks/{task_id}/pipeline-transition",
            json={"status": "implementing"},
        )
        assert resp.status_code == 409
        assert "backlog" in resp.json()["detail"]
        assert "implementing" in resp.json()["detail"]

    async def test_nonexistent_task_404(self, client: AsyncClient):
        resp = await client.post(
            f"/api/tasks/{uuid.uuid4()}/pipeline-transition",
            json={"status": "grooming"},
        )
        assert resp.status_code == 404

    async def test_actor_recorded_in_log(self, client: AsyncClient, session: SessionModel):
        task_id = await self._create_task(client, session)
        await client.post(
            f"/api/tasks/{task_id}/pipeline-transition",
            json={"status": "grooming", "actor": "pm-session-abc"},
        )
        resp = await client.get(f"/api/tasks/{task_id}/pipeline-log")
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) == 1
        assert logs[0]["actor"] == "pm-session-abc"

    async def test_null_actor_in_log(self, client: AsyncClient, session: SessionModel):
        task_id = await self._create_task(client, session)
        await client.post(
            f"/api/tasks/{task_id}/pipeline-transition",
            json={"status": "grooming"},
        )
        resp = await client.get(f"/api/tasks/{task_id}/pipeline-log")
        logs = resp.json()
        assert logs[0]["actor"] is None

    async def test_full_pipeline_walkthrough(self, client: AsyncClient, session: SessionModel):
        task_id = await self._create_task(client, session)
        statuses = ["grooming", "groomed", "implementing", "testing", "accepting", "done"]
        for status in statuses:
            resp = await client.post(
                f"/api/tasks/{task_id}/pipeline-transition",
                json={"status": status},
            )
            assert resp.status_code == 200
            assert resp.json()["pipeline_status"] == status

        # Verify log has all 6 transitions
        resp = await client.get(f"/api/tasks/{task_id}/pipeline-log")
        assert len(resp.json()) == 6

    async def test_rejection_loop(self, client: AsyncClient, session: SessionModel):
        task_id = await self._create_task(client, session)
        # Advance to testing
        for status in ["grooming", "groomed", "implementing", "testing"]:
            await client.post(
                f"/api/tasks/{task_id}/pipeline-transition",
                json={"status": status},
            )

        # QA rejects back to implementing
        resp = await client.post(
            f"/api/tasks/{task_id}/pipeline-transition",
            json={"status": "implementing", "actor": "qa-session"},
        )
        assert resp.status_code == 200
        assert resp.json()["pipeline_status"] == "implementing"

        # SWE fixes, advance through testing -> accepting -> done
        for status in ["testing", "accepting", "done"]:
            resp = await client.post(
                f"/api/tasks/{task_id}/pipeline-transition",
                json={"status": status},
            )
            assert resp.status_code == 200

        assert resp.json()["pipeline_status"] == "done"


@pytest.mark.asyncio
class TestPipelineLogEndpoint:
    async def test_empty_log(self, client: AsyncClient, session: SessionModel):
        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "no transitions"},
        )
        task_id = resp.json()["id"]
        resp = await client.get(f"/api/tasks/{task_id}/pipeline-log")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_chronological_order(self, client: AsyncClient, session: SessionModel):
        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "ordered"},
        )
        task_id = resp.json()["id"]
        for status in ["grooming", "groomed", "implementing"]:
            await client.post(
                f"/api/tasks/{task_id}/pipeline-transition",
                json={"status": status},
            )
        resp = await client.get(f"/api/tasks/{task_id}/pipeline-log")
        logs = resp.json()
        assert len(logs) == 3
        assert logs[0]["from_status"] == "backlog"
        assert logs[0]["to_status"] == "grooming"
        assert logs[1]["from_status"] == "grooming"
        assert logs[1]["to_status"] == "groomed"
        assert logs[2]["from_status"] == "groomed"
        assert logs[2]["to_status"] == "implementing"

    async def test_nonexistent_task_404(self, client: AsyncClient):
        resp = await client.get(f"/api/tasks/{uuid.uuid4()}/pipeline-log")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestTaskReadIncludesPipelineStatus:
    async def test_default_backlog(self, client: AsyncClient, session: SessionModel):
        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "default status"},
        )
        assert resp.status_code == 201
        assert resp.json()["pipeline_status"] == "backlog"

    async def test_explicit_pipeline_status(self, client: AsyncClient, session: SessionModel):
        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "groomed task", "pipeline_status": "groomed"},
        )
        assert resp.status_code == 201
        assert resp.json()["pipeline_status"] == "groomed"

    async def test_invalid_pipeline_status_422(self, client: AsyncClient, session: SessionModel):
        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "bad status", "pipeline_status": "invalid_status"},
        )
        assert resp.status_code == 422

    async def test_get_task_includes_pipeline_status(
        self, client: AsyncClient, session: SessionModel
    ):
        create_resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "check get"},
        )
        task_id = create_resp.json()["id"]
        resp = await client.get(f"/api/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["pipeline_status"] == "backlog"


@pytest.mark.asyncio
class TestListTasksPipelineFilter:
    async def test_filter_by_pipeline_status(self, client: AsyncClient, session: SessionModel):
        # Create tasks with different pipeline statuses
        await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "backlog task"},
        )
        await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "groomed task", "pipeline_status": "groomed"},
        )
        await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "another groomed", "pipeline_status": "groomed"},
        )

        # Filter for groomed only
        resp = await client.get(
            f"/api/sessions/{session.id}/tasks",
            params={"pipeline_status": "groomed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(t["pipeline_status"] == "groomed" for t in data)

    async def test_no_filter_returns_all(self, client: AsyncClient, session: SessionModel):
        await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "t1"},
        )
        await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "t2", "pipeline_status": "groomed"},
        )

        resp = await client.get(f"/api/sessions/{session.id}/tasks")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


@pytest.mark.asyncio
class TestExistingStatusUnaffected:
    """Verify that pipeline changes do not affect the existing task status field."""

    async def test_pipeline_transition_does_not_change_status(
        self, client: AsyncClient, session: SessionModel
    ):
        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "t"},
        )
        task_id = resp.json()["id"]
        assert resp.json()["status"] == "pending"

        # Pipeline transition
        resp = await client.post(
            f"/api/tasks/{task_id}/pipeline-transition",
            json={"status": "grooming"},
        )
        assert resp.json()["status"] == "pending"  # unchanged
        assert resp.json()["pipeline_status"] == "grooming"

    async def test_status_transition_does_not_change_pipeline(
        self, client: AsyncClient, session: SessionModel
    ):
        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "t"},
        )
        task_id = resp.json()["id"]

        # Status transition
        resp = await client.post(
            f"/api/tasks/{task_id}/transition",
            json={"status": "running"},
        )
        assert resp.json()["status"] == "running"
        assert resp.json()["pipeline_status"] == "backlog"  # unchanged
