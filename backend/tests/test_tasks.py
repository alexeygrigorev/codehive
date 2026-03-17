"""Tests for Task Queue API endpoints and core logic."""

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
    InvalidDependencyError,
    InvalidStatusTransitionError,
    SessionNotFoundError,
    TaskNotFoundError,
    create_task,
    delete_task,
    get_next_task,
    get_task,
    list_tasks,
    reorder_tasks,
    transition_task,
    update_task,
)
from codehive.db.models import Base, Project, Workspace
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database
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
async def workspace(db_session: AsyncSession) -> Workspace:
    """Create a workspace for tests."""
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
    """Create a project for task tests."""
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
async def session(db_session: AsyncSession, project: Project) -> SessionModel:
    """Create a session for task tests."""
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
async def other_session(db_session: AsyncSession, project: Project) -> SessionModel:
    """Create a second session in the same project (for cross-session tests)."""
    s = SessionModel(
        project_id=project.id,
        name="other-session",
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
    """Create an async test client with the DB session overridden."""
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
# Unit tests: Core task queue operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreCreateTask:
    async def test_create_task_success(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="Do something")
        assert task.id is not None
        assert isinstance(task.id, uuid.UUID)
        assert task.title == "Do something"
        assert task.status == "pending"
        assert task.priority == 0
        assert task.mode == "auto"
        assert task.created_by == "user"
        assert task.instructions is None
        assert task.depends_on is None
        assert task.created_at is not None

    async def test_create_task_with_all_fields(
        self, db_session: AsyncSession, session: SessionModel
    ):
        dep = await create_task(db_session, session_id=session.id, title="Dep task")
        task = await create_task(
            db_session,
            session_id=session.id,
            title="Full task",
            instructions="Do this carefully",
            priority=5,
            depends_on=dep.id,
            mode="manual",
            created_by="agent",
        )
        assert task.title == "Full task"
        assert task.instructions == "Do this carefully"
        assert task.priority == 5
        assert task.depends_on == dep.id
        assert task.mode == "manual"
        assert task.created_by == "agent"

    async def test_create_task_nonexistent_session(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await create_task(db_session, session_id=uuid.uuid4(), title="orphan")

    async def test_create_task_nonexistent_depends_on(
        self, db_session: AsyncSession, session: SessionModel
    ):
        with pytest.raises(TaskNotFoundError):
            await create_task(
                db_session,
                session_id=session.id,
                title="bad dep",
                depends_on=uuid.uuid4(),
            )

    async def test_create_task_depends_on_different_session(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        other_session: SessionModel,
    ):
        other_task = await create_task(db_session, session_id=other_session.id, title="other task")
        with pytest.raises(InvalidDependencyError):
            await create_task(
                db_session,
                session_id=session.id,
                title="cross-session dep",
                depends_on=other_task.id,
            )


@pytest.mark.asyncio
class TestCoreListTasks:
    async def test_list_ordered(self, db_session: AsyncSession, session: SessionModel):
        await create_task(db_session, session_id=session.id, title="low", priority=1)
        await create_task(db_session, session_id=session.id, title="high", priority=10)
        await create_task(db_session, session_id=session.id, title="mid", priority=5)
        tasks = await list_tasks(db_session, session.id)
        assert len(tasks) == 3
        assert tasks[0].title == "high"
        assert tasks[1].title == "mid"
        assert tasks[2].title == "low"

    async def test_list_empty(self, db_session: AsyncSession, session: SessionModel):
        tasks = await list_tasks(db_session, session.id)
        assert tasks == []

    async def test_list_nonexistent_session(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await list_tasks(db_session, uuid.uuid4())


@pytest.mark.asyncio
class TestCoreGetTask:
    async def test_get_existing(self, db_session: AsyncSession, session: SessionModel):
        created = await create_task(db_session, session_id=session.id, title="find me")
        found = await get_task(db_session, created.id)
        assert found is not None
        assert found.id == created.id

    async def test_get_nonexistent(self, db_session: AsyncSession):
        result = await get_task(db_session, uuid.uuid4())
        assert result is None


@pytest.mark.asyncio
class TestCoreUpdateTask:
    async def test_update_partial(self, db_session: AsyncSession, session: SessionModel):
        created = await create_task(db_session, session_id=session.id, title="orig", priority=0)
        updated = await update_task(db_session, created.id, priority=10)
        assert updated.priority == 10
        assert updated.title == "orig"  # unchanged

    async def test_update_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(TaskNotFoundError):
            await update_task(db_session, uuid.uuid4(), title="x")


@pytest.mark.asyncio
class TestCoreDeleteTask:
    async def test_delete_success(self, db_session: AsyncSession, session: SessionModel):
        created = await create_task(db_session, session_id=session.id, title="del me")
        await delete_task(db_session, created.id)
        assert await get_task(db_session, created.id) is None

    async def test_delete_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(TaskNotFoundError):
            await delete_task(db_session, uuid.uuid4())


@pytest.mark.asyncio
class TestCoreTransitionTask:
    async def test_pending_to_running(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        result = await transition_task(db_session, task.id, "running")
        assert result.status == "running"

    async def test_pending_to_blocked(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        result = await transition_task(db_session, task.id, "blocked")
        assert result.status == "blocked"

    async def test_pending_to_skipped(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        result = await transition_task(db_session, task.id, "skipped")
        assert result.status == "skipped"

    async def test_running_to_done(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await transition_task(db_session, task.id, "running")
        result = await transition_task(db_session, task.id, "done")
        assert result.status == "done"

    async def test_running_to_failed(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await transition_task(db_session, task.id, "running")
        result = await transition_task(db_session, task.id, "failed")
        assert result.status == "failed"

    async def test_running_to_blocked(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await transition_task(db_session, task.id, "running")
        result = await transition_task(db_session, task.id, "blocked")
        assert result.status == "blocked"

    async def test_blocked_to_pending(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await transition_task(db_session, task.id, "blocked")
        result = await transition_task(db_session, task.id, "pending")
        assert result.status == "pending"

    async def test_failed_to_pending(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "failed")
        result = await transition_task(db_session, task.id, "pending")
        assert result.status == "pending"

    async def test_done_is_terminal(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "done")
        with pytest.raises(InvalidStatusTransitionError):
            await transition_task(db_session, task.id, "pending")

    async def test_skipped_is_terminal(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        await transition_task(db_session, task.id, "skipped")
        with pytest.raises(InvalidStatusTransitionError):
            await transition_task(db_session, task.id, "pending")

    async def test_pending_to_done_invalid(self, db_session: AsyncSession, session: SessionModel):
        task = await create_task(db_session, session_id=session.id, title="t")
        with pytest.raises(InvalidStatusTransitionError):
            await transition_task(db_session, task.id, "done")

    async def test_transition_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(TaskNotFoundError):
            await transition_task(db_session, uuid.uuid4(), "running")


@pytest.mark.asyncio
class TestCoreGetNextTask:
    async def test_next_highest_priority(self, db_session: AsyncSession, session: SessionModel):
        await create_task(db_session, session_id=session.id, title="low", priority=1)
        await create_task(db_session, session_id=session.id, title="high", priority=10)
        task = await get_next_task(db_session, session.id)
        assert task is not None
        assert task.title == "high"

    async def test_next_skips_unmet_dependency(
        self, db_session: AsyncSession, session: SessionModel
    ):
        dep = await create_task(db_session, session_id=session.id, title="dep", priority=1)
        await create_task(
            db_session,
            session_id=session.id,
            title="blocked-by-dep",
            priority=10,
            depends_on=dep.id,
        )
        # dep is still pending, so blocked-by-dep should be skipped
        task = await get_next_task(db_session, session.id)
        assert task is not None
        assert task.title == "dep"

    async def test_next_returns_task_with_done_dependency(
        self, db_session: AsyncSession, session: SessionModel
    ):
        dep = await create_task(db_session, session_id=session.id, title="dep", priority=1)
        await create_task(
            db_session,
            session_id=session.id,
            title="after-dep",
            priority=10,
            depends_on=dep.id,
        )
        # Mark dep as done
        await transition_task(db_session, dep.id, "running")
        await transition_task(db_session, dep.id, "done")
        task = await get_next_task(db_session, session.id)
        assert task is not None
        assert task.title == "after-dep"

    async def test_next_none_when_all_done(self, db_session: AsyncSession, session: SessionModel):
        t = await create_task(db_session, session_id=session.id, title="t")
        await transition_task(db_session, t.id, "running")
        await transition_task(db_session, t.id, "done")
        result = await get_next_task(db_session, session.id)
        assert result is None

    async def test_next_none_when_all_running(
        self, db_session: AsyncSession, session: SessionModel
    ):
        t = await create_task(db_session, session_id=session.id, title="t")
        await transition_task(db_session, t.id, "running")
        result = await get_next_task(db_session, session.id)
        assert result is None

    async def test_next_none_when_all_blocked(
        self, db_session: AsyncSession, session: SessionModel
    ):
        t = await create_task(db_session, session_id=session.id, title="t")
        await transition_task(db_session, t.id, "blocked")
        result = await get_next_task(db_session, session.id)
        assert result is None

    async def test_next_nonexistent_session(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await get_next_task(db_session, uuid.uuid4())


@pytest.mark.asyncio
class TestCoreReorderTasks:
    async def test_reorder_success(self, db_session: AsyncSession, session: SessionModel):
        t1 = await create_task(db_session, session_id=session.id, title="t1", priority=1)
        t2 = await create_task(db_session, session_id=session.id, title="t2", priority=2)
        tasks = await reorder_tasks(
            db_session,
            session.id,
            [{"id": t1.id, "priority": 20}, {"id": t2.id, "priority": 10}],
        )
        assert tasks[0].title == "t1"
        assert tasks[0].priority == 20
        assert tasks[1].title == "t2"
        assert tasks[1].priority == 10

    async def test_reorder_cross_session(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        other_session: SessionModel,
    ):
        other_task = await create_task(db_session, session_id=other_session.id, title="other")
        with pytest.raises(InvalidDependencyError):
            await reorder_tasks(
                db_session,
                session.id,
                [{"id": other_task.id, "priority": 5}],
            )

    async def test_reorder_nonexistent_session(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await reorder_tasks(
                db_session,
                uuid.uuid4(),
                [{"id": uuid.uuid4(), "priority": 1}],
            )


# ---------------------------------------------------------------------------
# Integration tests: API endpoints via AsyncClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateTaskEndpoint:
    async def test_create_201(self, client: AsyncClient, session: SessionModel):
        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "My task"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My task"
        assert data["status"] == "pending"
        assert data["priority"] == 0
        assert data["mode"] == "auto"
        assert data["created_by"] == "user"
        assert data["session_id"] == str(session.id)
        assert "id" in data
        assert "created_at" in data

    async def test_create_with_all_optional_fields(
        self, client: AsyncClient, session: SessionModel
    ):
        # Create a dependency task first
        dep_resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "dep"},
        )
        dep_id = dep_resp.json()["id"]

        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={
                "title": "Full task",
                "instructions": "Do carefully",
                "priority": 5,
                "depends_on": dep_id,
                "mode": "manual",
                "created_by": "agent",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["instructions"] == "Do carefully"
        assert data["priority"] == 5
        assert data["depends_on"] == dep_id
        assert data["mode"] == "manual"
        assert data["created_by"] == "agent"

    async def test_create_missing_title_422(self, client: AsyncClient, session: SessionModel):
        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={},
        )
        assert resp.status_code == 422

    async def test_create_bad_session_404(self, client: AsyncClient):
        resp = await client.post(
            f"/api/sessions/{uuid.uuid4()}/tasks",
            json={"title": "orphan"},
        )
        assert resp.status_code == 404

    async def test_create_bad_depends_on_404(self, client: AsyncClient, session: SessionModel):
        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "bad dep", "depends_on": str(uuid.uuid4())},
        )
        assert resp.status_code == 404

    async def test_create_cross_session_depends_on_422(
        self, client: AsyncClient, session: SessionModel, other_session: SessionModel
    ):
        # Create a task in other_session
        dep_resp = await client.post(
            f"/api/sessions/{other_session.id}/tasks",
            json={"title": "other task"},
        )
        dep_id = dep_resp.json()["id"]

        resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "cross dep", "depends_on": dep_id},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestListTasksEndpoint:
    async def test_list_empty_200(self, client: AsyncClient, session: SessionModel):
        resp = await client.get(f"/api/sessions/{session.id}/tasks")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_ordered(self, client: AsyncClient, session: SessionModel):
        await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "low", "priority": 1},
        )
        await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "high", "priority": 10},
        )
        await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "mid", "priority": 5},
        )
        resp = await client.get(f"/api/sessions/{session.id}/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["title"] == "high"
        assert data[1]["title"] == "mid"
        assert data[2]["title"] == "low"

    async def test_list_bad_session_404(self, client: AsyncClient):
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/tasks")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestGetNextTaskEndpoint:
    async def test_next_200(self, client: AsyncClient, session: SessionModel):
        await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "low", "priority": 1},
        )
        await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "high", "priority": 10},
        )
        resp = await client.get(f"/api/sessions/{session.id}/tasks/next")
        assert resp.status_code == 200
        assert resp.json()["title"] == "high"

    async def test_next_204_when_none(self, client: AsyncClient, session: SessionModel):
        resp = await client.get(f"/api/sessions/{session.id}/tasks/next")
        assert resp.status_code == 204

    async def test_next_with_dependency_chain(self, client: AsyncClient, session: SessionModel):
        dep_resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "dep", "priority": 1},
        )
        dep_id = dep_resp.json()["id"]

        await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "after-dep", "priority": 10, "depends_on": dep_id},
        )

        # dep is pending, so next should be dep (lower priority but actionable)
        resp = await client.get(f"/api/sessions/{session.id}/tasks/next")
        assert resp.status_code == 200
        assert resp.json()["title"] == "dep"

        # Complete dep, then after-dep should be next
        await client.post(f"/api/tasks/{dep_id}/transition", json={"status": "running"})
        await client.post(f"/api/tasks/{dep_id}/transition", json={"status": "done"})

        resp = await client.get(f"/api/sessions/{session.id}/tasks/next")
        assert resp.status_code == 200
        assert resp.json()["title"] == "after-dep"

    async def test_next_bad_session_404(self, client: AsyncClient):
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/tasks/next")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestGetTaskEndpoint:
    async def test_get_200(self, client: AsyncClient, session: SessionModel):
        create_resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "getme"},
        )
        task_id = create_resp.json()["id"]
        resp = await client.get(f"/api/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "getme"

    async def test_get_404(self, client: AsyncClient):
        resp = await client.get(f"/api/tasks/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUpdateTaskEndpoint:
    async def test_patch_200(self, client: AsyncClient, session: SessionModel):
        create_resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "patchme"},
        )
        task_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/tasks/{task_id}",
            json={"priority": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["priority"] == 10
        assert resp.json()["title"] == "patchme"  # unchanged

    async def test_patch_404(self, client: AsyncClient):
        resp = await client.patch(
            f"/api/tasks/{uuid.uuid4()}",
            json={"priority": 10},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDeleteTaskEndpoint:
    async def test_delete_204_then_404(self, client: AsyncClient, session: SessionModel):
        create_resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "deleteme"},
        )
        task_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/tasks/{task_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/tasks/{task_id}")
        assert resp.status_code == 404

    async def test_delete_404(self, client: AsyncClient):
        resp = await client.delete(f"/api/tasks/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestTransitionTaskEndpoint:
    async def test_transition_pending_to_running(self, client: AsyncClient, session: SessionModel):
        create_resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "trans"},
        )
        task_id = create_resp.json()["id"]
        resp = await client.post(
            f"/api/tasks/{task_id}/transition",
            json={"status": "running"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    async def test_transition_pending_to_done_409(self, client: AsyncClient, session: SessionModel):
        create_resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "bad-trans"},
        )
        task_id = create_resp.json()["id"]
        resp = await client.post(
            f"/api/tasks/{task_id}/transition",
            json={"status": "done"},
        )
        assert resp.status_code == 409

    async def test_transition_from_done_409(self, client: AsyncClient, session: SessionModel):
        create_resp = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "terminal"},
        )
        task_id = create_resp.json()["id"]
        await client.post(f"/api/tasks/{task_id}/transition", json={"status": "running"})
        await client.post(f"/api/tasks/{task_id}/transition", json={"status": "done"})
        resp = await client.post(
            f"/api/tasks/{task_id}/transition",
            json={"status": "pending"},
        )
        assert resp.status_code == 409

    async def test_transition_404(self, client: AsyncClient):
        resp = await client.post(
            f"/api/tasks/{uuid.uuid4()}/transition",
            json={"status": "running"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestReorderTasksEndpoint:
    async def test_reorder_200(self, client: AsyncClient, session: SessionModel):
        r1 = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "t1", "priority": 1},
        )
        r2 = await client.post(
            f"/api/sessions/{session.id}/tasks",
            json={"title": "t2", "priority": 2},
        )
        t1_id = r1.json()["id"]
        t2_id = r2.json()["id"]

        resp = await client.post(
            f"/api/sessions/{session.id}/tasks/reorder",
            json=[
                {"id": t1_id, "priority": 20},
                {"id": t2_id, "priority": 10},
            ],
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should be ordered by priority desc
        assert data[0]["title"] == "t1"
        assert data[0]["priority"] == 20
        assert data[1]["title"] == "t2"
        assert data[1]["priority"] == 10

        # Verify via list
        list_resp = await client.get(f"/api/sessions/{session.id}/tasks")
        assert list_resp.json()[0]["priority"] == 20

    async def test_reorder_cross_session_422(
        self, client: AsyncClient, session: SessionModel, other_session: SessionModel
    ):
        r = await client.post(
            f"/api/sessions/{other_session.id}/tasks",
            json={"title": "other"},
        )
        other_id = r.json()["id"]

        resp = await client.post(
            f"/api/sessions/{session.id}/tasks/reorder",
            json=[{"id": other_id, "priority": 5}],
        )
        assert resp.status_code == 422

    async def test_reorder_bad_session_404(self, client: AsyncClient):
        resp = await client.post(
            f"/api/sessions/{uuid.uuid4()}/tasks/reorder",
            json=[{"id": str(uuid.uuid4()), "priority": 1}],
        )
        assert resp.status_code == 404
