"""Tests for archive/unarchive/delete projects and delete sessions (issue #156)."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.project import (
    ProjectNotFoundError,
    archive_project,
    create_project,
    delete_project,
    get_project,
    list_archived_projects,
    list_projects,
    unarchive_project,
)
from codehive.core.session import (
    SessionHasDependentsError,
    SessionNotFoundError,
    create_session,
    delete_session,
    get_session,
)
from codehive.db.models import (
    Base,
    Checkpoint,
    Event,
    Issue,
    IssueLogEntry,
    Message,
    PendingQuestion,
    Project,
    UsageRecord,
)
from codehive.db.models import Session as SessionModel

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
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


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
# Unit: Archive / Unarchive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreArchiveProject:
    async def test_archive_sets_timestamp(self, db_session: AsyncSession, project: Project):
        result = await archive_project(db_session, project.id)
        assert result.archived_at is not None
        assert isinstance(result.archived_at, datetime)

    async def test_archive_idempotent(self, db_session: AsyncSession, project: Project):
        first = await archive_project(db_session, project.id)
        ts1 = first.archived_at
        second = await archive_project(db_session, project.id)
        assert second.archived_at == ts1  # timestamp unchanged

    async def test_archive_nonexistent_404(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await archive_project(db_session, uuid.uuid4())

    async def test_unarchive_clears_timestamp(self, db_session: AsyncSession, project: Project):
        await archive_project(db_session, project.id)
        result = await unarchive_project(db_session, project.id)
        assert result.archived_at is None

    async def test_unarchive_idempotent(self, db_session: AsyncSession, project: Project):
        result = await unarchive_project(db_session, project.id)
        assert result.archived_at is None

    async def test_unarchive_nonexistent_404(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await unarchive_project(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Unit: Project delete with cascade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreDeleteProjectCascade:
    async def test_delete_project_with_sessions_and_issues(
        self, db_session: AsyncSession, project: Project
    ):
        """Deleting a project cascades to sessions, issues, and their children."""
        # Create a session with messages and events
        sess = SessionModel(
            project_id=project.id,
            name="s1",
            engine="native",
            mode="execution",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(sess)
        await db_session.flush()

        msg = Message(
            session_id=sess.id,
            role="user",
            content="hello",
            metadata_={},
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(msg)

        evt = Event(
            session_id=sess.id,
            type="test",
            data={},
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(evt)

        # Create an issue with a log entry
        iss = Issue(
            project_id=project.id,
            title="test-issue",
            status="open",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(iss)
        await db_session.flush()

        log_entry = IssueLogEntry(
            issue_id=iss.id,
            agent_role="swe",
            content="did stuff",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add(log_entry)
        await db_session.commit()

        # Delete the project
        await delete_project(db_session, project.id)

        # Clear identity map so we query fresh from DB
        db_session.expunge_all()

        # Verify everything is gone (use raw selects to avoid identity map)
        result = await db_session.execute(select(Project).where(Project.id == project.id))
        assert result.scalar_one_or_none() is None

        result = await db_session.execute(select(SessionModel).where(SessionModel.id == sess.id))
        assert result.scalar_one_or_none() is None

        result = await db_session.execute(select(Message).where(Message.id == msg.id))
        assert result.scalar_one_or_none() is None

        result = await db_session.execute(select(Issue).where(Issue.id == iss.id))
        assert result.scalar_one_or_none() is None

    async def test_delete_project_no_dependents(self, db_session: AsyncSession, project: Project):
        await delete_project(db_session, project.id)
        assert await get_project(db_session, project.id) is None

    async def test_delete_nonexistent_404(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await delete_project(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Unit: Session delete with cascade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreDeleteSessionCascade:
    async def test_delete_session_cascades_children(
        self, db_session: AsyncSession, project: Project
    ):
        """Deleting a session removes messages, events, checkpoints, etc."""
        sess = await create_session(
            db_session, project_id=project.id, name="s", engine="native", mode="execution"
        )

        msg = Message(
            session_id=sess.id,
            role="user",
            content="hello",
            metadata_={},
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        evt = Event(
            session_id=sess.id,
            type="test",
            data={},
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        ckpt = Checkpoint(
            session_id=sess.id,
            git_ref="abc123",
            state={},
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        pq = PendingQuestion(
            session_id=sess.id,
            question="what?",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        usage = UsageRecord(
            session_id=sess.id,
            model="test-model",
            input_tokens=10,
            output_tokens=20,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db_session.add_all([msg, evt, ckpt, pq, usage])
        await db_session.commit()

        await delete_session(db_session, sess.id)

        assert await get_session(db_session, sess.id) is None
        for model_cls, obj_id in [
            (Message, msg.id),
            (Event, evt.id),
            (Checkpoint, ckpt.id),
            (PendingQuestion, pq.id),
            (UsageRecord, usage.id),
        ]:
            result = await db_session.execute(select(model_cls).where(model_cls.id == obj_id))
            assert result.scalar_one_or_none() is None

    async def test_delete_session_with_child_sessions_409(
        self, db_session: AsyncSession, project: Project
    ):
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

    async def test_delete_nonexistent_session_404(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await delete_session(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Unit: List projects filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListProjectsFiltering:
    async def test_list_excludes_archived(self, db_session: AsyncSession):
        await create_project(db_session, name="active")
        p2 = await create_project(db_session, name="archived")
        await archive_project(db_session, p2.id)

        projects = await list_projects(db_session)
        # list_projects returns all -- filtering is at the API layer
        assert len(projects) == 2

    async def test_list_archived_only(self, db_session: AsyncSession):
        await create_project(db_session, name="active")
        p2 = await create_project(db_session, name="archived")
        await archive_project(db_session, p2.id)

        archived = await list_archived_projects(db_session)
        assert len(archived) == 1
        assert archived[0].name == "archived"

    async def test_list_archived_empty(self, db_session: AsyncSession):
        await create_project(db_session, name="active")
        archived = await list_archived_projects(db_session)
        assert archived == []


# ---------------------------------------------------------------------------
# Integration: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestArchiveEndpoints:
    async def test_archive_returns_200(self, client: AsyncClient):
        resp = await client.post("/api/projects", json={"name": "arch-me"})
        pid = resp.json()["id"]

        resp = await client.post(f"/api/projects/{pid}/archive")
        assert resp.status_code == 200
        assert resp.json()["archived_at"] is not None

    async def test_unarchive_returns_200(self, client: AsyncClient):
        resp = await client.post("/api/projects", json={"name": "unarch-me"})
        pid = resp.json()["id"]

        await client.post(f"/api/projects/{pid}/archive")
        resp = await client.post(f"/api/projects/{pid}/unarchive")
        assert resp.status_code == 200
        assert resp.json()["archived_at"] is None

    async def test_archive_nonexistent_404(self, client: AsyncClient):
        resp = await client.post(f"/api/projects/{uuid.uuid4()}/archive")
        assert resp.status_code == 404

    async def test_unarchive_nonexistent_404(self, client: AsyncClient):
        resp = await client.post(f"/api/projects/{uuid.uuid4()}/unarchive")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestListProjectsFilterEndpoints:
    async def test_list_excludes_archived_by_default(self, client: AsyncClient):
        await client.post("/api/projects", json={"name": "active"})
        resp2 = await client.post("/api/projects", json={"name": "archived"})
        await client.post(f"/api/projects/{resp2.json()['id']}/archive")

        resp = await client.get("/api/projects")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "active" in names
        assert "archived" not in names

    async def test_list_include_archived(self, client: AsyncClient):
        await client.post("/api/projects", json={"name": "active2"})
        resp2 = await client.post("/api/projects", json={"name": "archived2"})
        await client.post(f"/api/projects/{resp2.json()['id']}/archive")

        resp = await client.get("/api/projects?include_archived=true")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "active2" in names
        assert "archived2" in names

    async def test_list_archived_endpoint(self, client: AsyncClient):
        await client.post("/api/projects", json={"name": "active3"})
        resp2 = await client.post("/api/projects", json={"name": "archived3"})
        await client.post(f"/api/projects/{resp2.json()['id']}/archive")

        resp = await client.get("/api/projects/archived")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "archived3" in names
        assert "active3" not in names

    async def test_archived_endpoint_empty(self, client: AsyncClient):
        await client.post("/api/projects", json={"name": "not-archived"})
        resp = await client.get("/api/projects/archived")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
class TestDeleteProjectCascadeEndpoint:
    async def test_delete_with_sessions_204(self, client: AsyncClient):
        """DELETE /api/projects/{id} cascades to sessions."""
        resp = await client.post("/api/projects", json={"name": "cascade-me"})
        pid = resp.json()["id"]

        await client.post(
            f"/api/projects/{pid}/sessions",
            json={"name": "s1", "engine": "native", "mode": "execution"},
        )

        resp = await client.delete(f"/api/projects/{pid}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/projects/{pid}")
        assert resp.status_code == 404

    async def test_delete_nonexistent_404(self, client: AsyncClient):
        resp = await client.delete(f"/api/projects/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDeleteSessionEndpointCascade:
    async def test_delete_session_204(self, client: AsyncClient):
        resp = await client.post("/api/projects", json={"name": "sess-del"})
        pid = resp.json()["id"]

        resp = await client.post(
            f"/api/projects/{pid}/sessions",
            json={"name": "del-me", "engine": "native", "mode": "execution"},
        )
        sid = resp.json()["id"]

        resp = await client.delete(f"/api/sessions/{sid}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/sessions/{sid}")
        assert resp.status_code == 404

    async def test_delete_session_with_children_409(self, client: AsyncClient):
        resp = await client.post("/api/projects", json={"name": "child-test"})
        pid = resp.json()["id"]

        resp = await client.post(
            f"/api/projects/{pid}/sessions",
            json={"name": "parent", "engine": "native", "mode": "execution"},
        )
        parent_id = resp.json()["id"]

        await client.post(
            f"/api/projects/{pid}/sessions",
            json={
                "name": "child",
                "engine": "native",
                "mode": "execution",
                "parent_session_id": parent_id,
            },
        )

        resp = await client.delete(f"/api/sessions/{parent_id}")
        assert resp.status_code == 409

    async def test_delete_session_nonexistent_404(self, client: AsyncClient):
        resp = await client.delete(f"/api/sessions/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestFullFlow:
    async def test_create_archive_unarchive_delete(self, client: AsyncClient):
        """Full flow: create -> add session -> archive -> hidden -> unarchive -> visible -> delete -> gone."""
        # Create project
        resp = await client.post("/api/projects", json={"name": "full-flow"})
        assert resp.status_code == 201
        pid = resp.json()["id"]

        # Create session
        resp = await client.post(
            f"/api/projects/{pid}/sessions",
            json={"name": "s1", "engine": "native", "mode": "execution"},
        )
        assert resp.status_code == 201

        # Archive
        resp = await client.post(f"/api/projects/{pid}/archive")
        assert resp.status_code == 200
        assert resp.json()["archived_at"] is not None

        # Verify hidden from default list
        resp = await client.get("/api/projects")
        names = [p["name"] for p in resp.json()]
        assert "full-flow" not in names

        # Verify visible in archived list
        resp = await client.get("/api/projects/archived")
        names = [p["name"] for p in resp.json()]
        assert "full-flow" in names

        # Unarchive
        resp = await client.post(f"/api/projects/{pid}/unarchive")
        assert resp.status_code == 200
        assert resp.json()["archived_at"] is None

        # Verify visible in default list
        resp = await client.get("/api/projects")
        names = [p["name"] for p in resp.json()]
        assert "full-flow" in names

        # Delete project (cascades to session)
        resp = await client.delete(f"/api/projects/{pid}")
        assert resp.status_code == 204

        # Verify gone
        resp = await client.get(f"/api/projects/{pid}")
        assert resp.status_code == 404
