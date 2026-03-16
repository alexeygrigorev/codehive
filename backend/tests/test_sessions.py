"""Tests for Session CRUD API endpoints and core logic."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.session import (
    InvalidStatusTransitionError,
    IssueNotFoundError,
    ProjectNotFoundError,
    SessionHasDependentsError,
    SessionNotFoundError,
    create_session,
    delete_session,
    get_session,
    list_sessions,
    pause_session,
    resume_session,
    update_session,
)
from codehive.db.models import Base, Issue, Project, Workspace
from codehive.db.models import Session as SessionModel
from tests.conftest import ensure_workspace_membership

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

        from sqlalchemy import Table

        Table(table.name, metadata, *columns)

    return metadata


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create tables in an in-memory SQLite DB and yield an async session."""
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
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
    """Create a project for session tests."""
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
async def issue(db_session: AsyncSession, project: Project) -> Issue:
    """Create an issue for session tests."""
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


@pytest_asyncio.fixture
async def project_member(
    project: Project, workspace: Workspace, client: AsyncClient, db_session: AsyncSession
) -> Project:
    """Ensure the test user is an owner of the workspace for API tests."""
    await ensure_workspace_membership(db_session, workspace.id)
    return project


# ---------------------------------------------------------------------------
# Unit tests: Core session operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreCreateSession:
    async def test_create_session_success(self, db_session: AsyncSession, project: Project):
        session = await create_session(
            db_session,
            project_id=project.id,
            name="my-session",
            engine="native",
            mode="execution",
        )
        assert session.id is not None
        assert isinstance(session.id, uuid.UUID)
        assert session.name == "my-session"
        assert session.engine == "native"
        assert session.mode == "execution"
        assert session.status == "idle"
        assert session.project_id == project.id
        assert session.config == {}
        assert session.created_at is not None

    async def test_create_session_nonexistent_project(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await create_session(
                db_session,
                project_id=uuid.uuid4(),
                name="orphan",
                engine="native",
                mode="execution",
            )

    async def test_create_session_nonexistent_issue(
        self, db_session: AsyncSession, project: Project
    ):
        with pytest.raises(IssueNotFoundError):
            await create_session(
                db_session,
                project_id=project.id,
                name="bad-issue",
                engine="native",
                mode="execution",
                issue_id=uuid.uuid4(),
            )

    async def test_create_session_nonexistent_parent(
        self, db_session: AsyncSession, project: Project
    ):
        with pytest.raises(SessionNotFoundError):
            await create_session(
                db_session,
                project_id=project.id,
                name="bad-parent",
                engine="native",
                mode="execution",
                parent_session_id=uuid.uuid4(),
            )

    async def test_create_session_with_issue_and_parent(
        self, db_session: AsyncSession, project: Project, issue: Issue
    ):
        parent = await create_session(
            db_session,
            project_id=project.id,
            name="parent",
            engine="native",
            mode="execution",
        )
        child = await create_session(
            db_session,
            project_id=project.id,
            name="child",
            engine="claude_code",
            mode="brainstorm",
            issue_id=issue.id,
            parent_session_id=parent.id,
            config={"key": "value"},
        )
        assert child.issue_id == issue.id
        assert child.parent_session_id == parent.id
        assert child.config == {"key": "value"}


@pytest.mark.asyncio
class TestCoreListSessions:
    async def test_list_empty(self, db_session: AsyncSession, project: Project):
        sessions = await list_sessions(db_session, project.id)
        assert sessions == []

    async def test_list_multiple(self, db_session: AsyncSession, project: Project):
        await create_session(
            db_session, project_id=project.id, name="s1", engine="native", mode="execution"
        )
        await create_session(
            db_session, project_id=project.id, name="s2", engine="native", mode="execution"
        )
        sessions = await list_sessions(db_session, project.id)
        assert len(sessions) == 2

    async def test_list_filters_by_project(
        self, db_session: AsyncSession, workspace: Workspace, project: Project
    ):
        """Sessions from other projects are not returned."""
        other_project = Project(
            workspace_id=workspace.id,
            name="other-project",
            knowledge={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(other_project)
        await db_session.commit()
        await db_session.refresh(other_project)

        await create_session(
            db_session, project_id=project.id, name="mine", engine="native", mode="execution"
        )
        await create_session(
            db_session,
            project_id=other_project.id,
            name="other",
            engine="native",
            mode="execution",
        )
        sessions = await list_sessions(db_session, project.id)
        assert len(sessions) == 1
        assert sessions[0].name == "mine"

    async def test_list_nonexistent_project(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await list_sessions(db_session, uuid.uuid4())


@pytest.mark.asyncio
class TestCoreGetSession:
    async def test_get_existing(self, db_session: AsyncSession, project: Project):
        created = await create_session(
            db_session, project_id=project.id, name="s", engine="native", mode="execution"
        )
        found = await get_session(db_session, created.id)
        assert found is not None
        assert found.id == created.id

    async def test_get_nonexistent(self, db_session: AsyncSession):
        result = await get_session(db_session, uuid.uuid4())
        assert result is None


@pytest.mark.asyncio
class TestCoreUpdateSession:
    async def test_update_partial(self, db_session: AsyncSession, project: Project):
        created = await create_session(
            db_session, project_id=project.id, name="orig", engine="native", mode="execution"
        )
        updated = await update_session(db_session, created.id, mode="review")
        assert updated.mode == "review"
        assert updated.name == "orig"  # unchanged

    async def test_update_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await update_session(db_session, uuid.uuid4(), name="x")


@pytest.mark.asyncio
class TestCoreDeleteSession:
    async def test_delete_success(self, db_session: AsyncSession, project: Project):
        created = await create_session(
            db_session, project_id=project.id, name="del-me", engine="native", mode="execution"
        )
        await delete_session(db_session, created.id)
        assert await get_session(db_session, created.id) is None

    async def test_delete_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await delete_session(db_session, uuid.uuid4())

    async def test_delete_with_children(self, db_session: AsyncSession, project: Project):
        parent = await create_session(
            db_session, project_id=project.id, name="parent", engine="native", mode="execution"
        )
        await create_session(
            db_session,
            project_id=project.id,
            name="child",
            engine="native",
            mode="execution",
            parent_session_id=parent.id,
        )
        with pytest.raises(SessionHasDependentsError):
            await delete_session(db_session, parent.id)


@pytest.mark.asyncio
class TestCorePauseSession:
    async def test_pause_from_idle(self, db_session: AsyncSession, project: Project):
        session = await create_session(
            db_session, project_id=project.id, name="s", engine="native", mode="execution"
        )
        paused = await pause_session(db_session, session.id)
        assert paused.status == "blocked"

    async def test_pause_from_completed(self, db_session: AsyncSession, project: Project):
        session = await create_session(
            db_session, project_id=project.id, name="s", engine="native", mode="execution"
        )
        # Manually set status to completed
        session.status = "completed"
        await db_session.commit()
        await db_session.refresh(session)

        with pytest.raises(InvalidStatusTransitionError):
            await pause_session(db_session, session.id)

    async def test_pause_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await pause_session(db_session, uuid.uuid4())


@pytest.mark.asyncio
class TestCoreResumeSession:
    async def test_resume_from_blocked(self, db_session: AsyncSession, project: Project):
        session = await create_session(
            db_session, project_id=project.id, name="s", engine="native", mode="execution"
        )
        await pause_session(db_session, session.id)
        resumed = await resume_session(db_session, session.id)
        assert resumed.status == "idle"

    async def test_resume_from_idle(self, db_session: AsyncSession, project: Project):
        session = await create_session(
            db_session, project_id=project.id, name="s", engine="native", mode="execution"
        )
        with pytest.raises(InvalidStatusTransitionError):
            await resume_session(db_session, session.id)

    async def test_resume_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await resume_session(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Integration tests: API endpoints via AsyncClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateSessionEndpoint:
    async def test_create_201(self, client: AsyncClient, project_member: Project):
        resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={
                "name": "api-session",
                "engine": "native",
                "mode": "execution",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "api-session"
        assert data["engine"] == "native"
        assert data["mode"] == "execution"
        assert data["status"] == "idle"
        assert data["project_id"] == str(project_member.id)
        assert data["config"] == {}
        assert "id" in data
        assert "created_at" in data

    async def test_create_missing_fields_422(self, client: AsyncClient, project_member: Project):
        resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "incomplete"},
        )
        assert resp.status_code == 422

    async def test_create_bad_project_404(self, client: AsyncClient):
        resp = await client.post(
            f"/api/projects/{uuid.uuid4()}/sessions",
            json={"name": "orphan", "engine": "native", "mode": "execution"},
        )
        assert resp.status_code == 404

    async def test_create_bad_issue_404(self, client: AsyncClient, project_member: Project):
        resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={
                "name": "bad-issue",
                "engine": "native",
                "mode": "execution",
                "issue_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 404

    async def test_create_bad_parent_session_404(
        self, client: AsyncClient, project_member: Project
    ):
        resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={
                "name": "bad-parent",
                "engine": "native",
                "mode": "execution",
                "parent_session_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestListSessionsEndpoint:
    async def test_list_empty_200(self, client: AsyncClient, project_member: Project):
        resp = await client.get(f"/api/projects/{project_member.id}/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_sessions(self, client: AsyncClient, project_member: Project):
        await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "s1", "engine": "native", "mode": "execution"},
        )
        await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "s2", "engine": "native", "mode": "execution"},
        )
        resp = await client.get(f"/api/projects/{project_member.id}/sessions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_list_bad_project_404(self, client: AsyncClient):
        resp = await client.get(f"/api/projects/{uuid.uuid4()}/sessions")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestGetSessionEndpoint:
    async def test_get_200(self, client: AsyncClient, project_member: Project):
        create_resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "getme", "engine": "native", "mode": "execution"},
        )
        session_id = create_resp.json()["id"]
        resp = await client.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "getme"

    async def test_get_404(self, client: AsyncClient):
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUpdateSessionEndpoint:
    async def test_patch_200(self, client: AsyncClient, project_member: Project):
        create_resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "patchme", "engine": "native", "mode": "execution"},
        )
        session_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/sessions/{session_id}",
            json={"mode": "review"},
        )
        assert resp.status_code == 200
        assert resp.json()["mode"] == "review"
        assert resp.json()["name"] == "patchme"  # unchanged

    async def test_patch_404(self, client: AsyncClient):
        resp = await client.patch(
            f"/api/sessions/{uuid.uuid4()}",
            json={"mode": "review"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDeleteSessionEndpoint:
    async def test_delete_204_then_404(self, client: AsyncClient, project_member: Project):
        create_resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "deleteme", "engine": "native", "mode": "execution"},
        )
        session_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/sessions/{session_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 404

    async def test_delete_404(self, client: AsyncClient):
        resp = await client.delete(f"/api/sessions/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_delete_with_children_409(self, client: AsyncClient, project_member: Project):
        # Create parent session
        parent_resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "parent", "engine": "native", "mode": "execution"},
        )
        parent_id = parent_resp.json()["id"]

        # Create child session
        await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={
                "name": "child",
                "engine": "native",
                "mode": "execution",
                "parent_session_id": parent_id,
            },
        )

        resp = await client.delete(f"/api/sessions/{parent_id}")
        assert resp.status_code == 409


@pytest.mark.asyncio
class TestPauseSessionEndpoint:
    async def test_pause_from_idle_200(self, client: AsyncClient, project_member: Project):
        create_resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "pauseme", "engine": "native", "mode": "execution"},
        )
        session_id = create_resp.json()["id"]

        resp = await client.post(f"/api/sessions/{session_id}/pause")
        assert resp.status_code == 200
        assert resp.json()["status"] == "blocked"

    async def test_pause_from_completed_409(
        self, client: AsyncClient, project_member: Project, db_session: AsyncSession
    ):
        create_resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "completed-s", "engine": "native", "mode": "execution"},
        )
        session_id = create_resp.json()["id"]

        # Manually set status to completed via DB
        s = await db_session.get(SessionModel, uuid.UUID(session_id))
        s.status = "completed"
        await db_session.commit()

        resp = await client.post(f"/api/sessions/{session_id}/pause")
        assert resp.status_code == 409

    async def test_pause_404(self, client: AsyncClient):
        resp = await client.post(f"/api/sessions/{uuid.uuid4()}/pause")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestResumeSessionEndpoint:
    async def test_resume_from_blocked_200(self, client: AsyncClient, project_member: Project):
        create_resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "resumeme", "engine": "native", "mode": "execution"},
        )
        session_id = create_resp.json()["id"]

        # First pause it
        await client.post(f"/api/sessions/{session_id}/pause")

        resp = await client.post(f"/api/sessions/{session_id}/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "idle"

    async def test_resume_from_idle_409(self, client: AsyncClient, project_member: Project):
        create_resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "idle-s", "engine": "native", "mode": "execution"},
        )
        session_id = create_resp.json()["id"]

        resp = await client.post(f"/api/sessions/{session_id}/resume")
        assert resp.status_code == 409

    async def test_resume_404(self, client: AsyncClient):
        resp = await client.post(f"/api/sessions/{uuid.uuid4()}/resume")
        assert resp.status_code == 404
