"""Tests for issue #142: Agent-Task Binding.

Covers model columns, create_session service, schema validation,
API endpoints, and orchestrator binding.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.api.schemas.session import SessionCreate, SessionRead
from codehive.core.session import (
    InvalidPipelineStepError,
    TaskNotFoundError,
    create_session,
    list_sessions_by_task,
)
from codehive.core.task_queue import create_task
from codehive.db.models import Base, Issue, Project, Task
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        # Disable FK checks during drop to handle circular session<->task FKs
        await conn.execute(text("PRAGMA foreign_keys=OFF"))
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(db_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with db_session_factory() as session:
        yield session


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
async def issue(db_session: AsyncSession, project: Project) -> Issue:
    iss = Issue(
        project_id=project.id,
        title="test-issue",
        status="open",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(iss)
    await db_session.commit()
    await db_session.refresh(iss)
    return iss


@pytest_asyncio.fixture
async def orch_session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name=f"orchestrator-{project.id}",
        engine="claude_code",
        mode="orchestrator",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def task(db_session: AsyncSession, orch_session: SessionModel) -> Task:
    return await create_task(
        db_session, session_id=orch_session.id, title="test-task", pipeline_status="backlog"
    )


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
            json={"email": "bind@test.com", "username": "binduser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit: Schema validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_session_create_valid_pipeline_step(self):
        sc = SessionCreate(
            name="s",
            engine="native",
            mode="execution",
            pipeline_step="grooming",
        )
        assert sc.pipeline_step == "grooming"

    def test_session_create_invalid_pipeline_step_raises(self):
        with pytest.raises(Exception, match="Invalid pipeline_step"):
            SessionCreate(
                name="s",
                engine="native",
                mode="execution",
                pipeline_step="unknown",
            )

    def test_session_create_none_pipeline_step_allowed(self):
        sc = SessionCreate(name="s", engine="native", mode="execution")
        assert sc.pipeline_step is None
        assert sc.task_id is None

    def test_session_read_includes_binding_fields(self):
        tid = uuid.uuid4()
        sr = SessionRead(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            issue_id=None,
            parent_session_id=None,
            task_id=tid,
            pipeline_step="implementing",
            name="s",
            role=None,
            engine="native",
            mode="execution",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        assert sr.task_id == tid
        assert sr.pipeline_step == "implementing"


# ---------------------------------------------------------------------------
# Unit: create_session service with binding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateSessionBinding:
    async def test_create_with_task_and_step(
        self, db_session: AsyncSession, project: Project, task: Task
    ):
        session = await create_session(
            db_session,
            project_id=project.id,
            name="bound-session",
            engine="native",
            mode="execution",
            task_id=task.id,
            pipeline_step="grooming",
        )
        assert session.task_id == task.id
        assert session.pipeline_step == "grooming"

    async def test_create_without_binding_backward_compatible(
        self, db_session: AsyncSession, project: Project
    ):
        session = await create_session(
            db_session,
            project_id=project.id,
            name="no-binding",
            engine="native",
            mode="execution",
        )
        assert session.task_id is None
        assert session.pipeline_step is None

    async def test_create_with_invalid_task_id_raises(
        self, db_session: AsyncSession, project: Project
    ):
        with pytest.raises(TaskNotFoundError):
            await create_session(
                db_session,
                project_id=project.id,
                name="bad-task",
                engine="native",
                mode="execution",
                task_id=uuid.uuid4(),
            )

    async def test_create_with_invalid_pipeline_step_raises(
        self, db_session: AsyncSession, project: Project
    ):
        with pytest.raises(InvalidPipelineStepError):
            await create_session(
                db_session,
                project_id=project.id,
                name="bad-step",
                engine="native",
                mode="execution",
                pipeline_step="invalid_step",
            )


# ---------------------------------------------------------------------------
# Unit: list_sessions_by_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListSessionsByTask:
    async def test_list_sessions_by_task(
        self, db_session: AsyncSession, project: Project, task: Task
    ):
        s1 = await create_session(
            db_session,
            project_id=project.id,
            name="s1",
            engine="native",
            mode="execution",
            task_id=task.id,
            pipeline_step="grooming",
        )
        s2 = await create_session(
            db_session,
            project_id=project.id,
            name="s2",
            engine="native",
            mode="execution",
            task_id=task.id,
            pipeline_step="implementing",
        )
        # Unbound session -- should not be returned
        await create_session(
            db_session,
            project_id=project.id,
            name="unbound",
            engine="native",
            mode="execution",
        )

        results = await list_sessions_by_task(db_session, task.id)
        ids = {s.id for s in results}
        assert s1.id in ids
        assert s2.id in ids
        assert len(results) == 2

    async def test_list_sessions_by_task_empty(self, db_session: AsyncSession):
        results = await list_sessions_by_task(db_session, uuid.uuid4())
        assert results == []


# ---------------------------------------------------------------------------
# Integration: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBindingAPI:
    async def test_create_session_with_binding_201(
        self, client: AsyncClient, project: Project, task: Task
    ):
        resp = await client.post(
            f"/api/projects/{project.id}/sessions",
            json={
                "name": "api-bound",
                "engine": "native",
                "mode": "execution",
                "task_id": str(task.id),
                "pipeline_step": "grooming",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_id"] == str(task.id)
        assert data["pipeline_step"] == "grooming"

    async def test_create_session_invalid_task_404(self, client: AsyncClient, project: Project):
        resp = await client.post(
            f"/api/projects/{project.id}/sessions",
            json={
                "name": "bad-task",
                "engine": "native",
                "mode": "execution",
                "task_id": str(uuid.uuid4()),
                "pipeline_step": "grooming",
            },
        )
        assert resp.status_code == 404
        assert "Task not found" in resp.json()["detail"]

    async def test_create_session_invalid_pipeline_step_422(
        self, client: AsyncClient, project: Project
    ):
        resp = await client.post(
            f"/api/projects/{project.id}/sessions",
            json={
                "name": "bad-step",
                "engine": "native",
                "mode": "execution",
                "pipeline_step": "unknown",
            },
        )
        assert resp.status_code == 422

    async def test_get_session_includes_binding(
        self, client: AsyncClient, project: Project, task: Task
    ):
        create_resp = await client.post(
            f"/api/projects/{project.id}/sessions",
            json={
                "name": "get-binding",
                "engine": "native",
                "mode": "execution",
                "task_id": str(task.id),
                "pipeline_step": "testing",
            },
        )
        session_id = create_resp.json()["id"]

        resp = await client.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == str(task.id)
        assert data["pipeline_step"] == "testing"

    async def test_list_sessions_by_task_endpoint(
        self, client: AsyncClient, project: Project, task: Task
    ):
        # Create two bound sessions
        await client.post(
            f"/api/projects/{project.id}/sessions",
            json={
                "name": "bound1",
                "engine": "native",
                "mode": "execution",
                "task_id": str(task.id),
                "pipeline_step": "grooming",
            },
        )
        await client.post(
            f"/api/projects/{project.id}/sessions",
            json={
                "name": "bound2",
                "engine": "native",
                "mode": "execution",
                "task_id": str(task.id),
                "pipeline_step": "implementing",
            },
        )
        # Create unbound session
        await client.post(
            f"/api/projects/{project.id}/sessions",
            json={"name": "unbound", "engine": "native", "mode": "execution"},
        )

        resp = await client.get(f"/api/sessions?task_id={task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {s["name"] for s in data}
        assert "bound1" in names
        assert "bound2" in names

    async def test_list_sessions_by_task_empty(self, client: AsyncClient):
        resp = await client.get(f"/api/sessions?task_id={uuid.uuid4()}")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_project_sessions_includes_binding(
        self, client: AsyncClient, project: Project, task: Task
    ):
        await client.post(
            f"/api/projects/{project.id}/sessions",
            json={
                "name": "listed",
                "engine": "native",
                "mode": "execution",
                "task_id": str(task.id),
                "pipeline_step": "accepting",
            },
        )

        resp = await client.get(f"/api/projects/{project.id}/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        bound = [s for s in data if s["name"] == "listed"][0]
        assert bound["task_id"] == str(task.id)
        assert bound["pipeline_step"] == "accepting"


# ---------------------------------------------------------------------------
# Integration: Orchestrator _default_spawn_and_run binding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrchestratorBinding:
    async def test_default_spawn_and_run_passes_binding(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        task: Task,
    ):
        """_default_spawn_and_run creates a child session with task_id and pipeline_step."""
        from codehive.core.orchestrator_service import OrchestratorService

        service = OrchestratorService(db_session_factory, project.id)

        await service._default_spawn_and_run(
            task_id=task.id,
            step="implementing",
            role="swe",
            mode="execution",
            instructions="Do stuff",
        )

        # Verify the child session was created with the binding
        async with db_session_factory() as db:
            sessions = await list_sessions_by_task(db, task.id)
            assert len(sessions) == 1
            child = sessions[0]
            assert child.task_id == task.id
            assert child.pipeline_step == "implementing"
            assert child.name == f"swe-implementing-{task.id}"

    async def test_pipeline_creates_bound_sessions(
        self,
        db_session_factory,
        db_session: AsyncSession,
        project: Project,
        orch_session: SessionModel,
        issue: Issue,
        task: Task,
    ):
        """Full pipeline creates sessions with correct task_id and pipeline_step."""
        from codehive.core.orchestrator_service import OrchestratorService

        orch_session.issue_id = issue.id
        await db_session.commit()

        # Track create_session calls
        created_sessions: list[dict] = []
        original_spawn = OrchestratorService._default_spawn_and_run

        async def tracking_spawn(self_inner, task_id, step, role, mode, instructions):
            await original_spawn(self_inner, task_id, step, role, mode, instructions)
            created_sessions.append({"task_id": task_id, "step": step})
            return "VERDICT: PASS" if step != "accepting" else "VERDICT: ACCEPT"

        service = OrchestratorService(db_session_factory, project.id)
        service._spawn_and_run = lambda **kw: tracking_spawn(service, **kw)

        await service._run_task_pipeline(task)

        # All 4 steps should have created bound sessions
        steps_seen = {s["step"] for s in created_sessions}
        assert "grooming" in steps_seen
        assert "implementing" in steps_seen
        assert "testing" in steps_seen
        assert "accepting" in steps_seen

        # All sessions should be bound to the task
        for entry in created_sessions:
            assert entry["task_id"] == task.id
