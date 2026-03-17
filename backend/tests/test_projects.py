"""Tests for Project CRUD API endpoints and core logic."""

import uuid
from collections.abc import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.project import (
    ProjectNotFoundError,
    WorkspaceNotFoundError,
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)
from codehive.db.models import Base, Workspace
from tests.conftest import ensure_workspace_membership

# All tests in this file require auth_enabled=True since they test permission behavior.
pytestmark = pytest.mark.usefixtures("_enable_auth")


@pytest.fixture(autouse=True)
def _enable_auth(monkeypatch):
    """Ensure auth is enabled for all tests in this module."""
    monkeypatch.setenv("CODEHIVE_AUTH_ENABLED", "true")


# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create tables in an in-memory SQLite DB and yield an async session."""
    engine = create_async_engine(SQLITE_URL)

    # SQLite needs PRAGMA for FK enforcement
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
    """Create a workspace for project tests."""
    from datetime import datetime, timezone

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
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with the DB session overridden.

    Automatically registers a test user and includes auth headers on all requests.
    """
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register a test user and get tokens
        resp = await ac.post(
            "/api/auth/register",
            json={"email": "test@test.com", "username": "testuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


@pytest_asyncio.fixture
async def workspace_member(
    workspace: Workspace, client: AsyncClient, db_session: AsyncSession
) -> Workspace:
    """Ensure the test user is an owner of the workspace for API tests."""
    await ensure_workspace_membership(db_session, workspace.id)
    return workspace


# ---------------------------------------------------------------------------
# Unit tests: Core project operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreCreateProject:
    async def test_create_project_success(self, db_session: AsyncSession, workspace: Workspace):
        project = await create_project(
            db_session,
            workspace_id=workspace.id,
            name="my-project",
            description="A test project",
        )
        assert project.id is not None
        assert isinstance(project.id, uuid.UUID)
        assert project.name == "my-project"
        assert project.workspace_id == workspace.id
        assert project.created_at is not None
        assert project.knowledge == {}

    async def test_create_project_nonexistent_workspace(self, db_session: AsyncSession):
        with pytest.raises(WorkspaceNotFoundError):
            await create_project(
                db_session,
                workspace_id=uuid.uuid4(),
                name="orphan",
            )


@pytest.mark.asyncio
class TestCoreListProjects:
    async def test_list_empty(self, db_session: AsyncSession):
        projects = await list_projects(db_session)
        assert projects == []

    async def test_list_multiple(self, db_session: AsyncSession, workspace: Workspace):
        await create_project(db_session, workspace_id=workspace.id, name="p1")
        await create_project(db_session, workspace_id=workspace.id, name="p2")
        projects = await list_projects(db_session)
        assert len(projects) == 2


@pytest.mark.asyncio
class TestCoreGetProject:
    async def test_get_existing(self, db_session: AsyncSession, workspace: Workspace):
        created = await create_project(db_session, workspace_id=workspace.id, name="proj")
        found = await get_project(db_session, created.id)
        assert found is not None
        assert found.id == created.id

    async def test_get_nonexistent(self, db_session: AsyncSession):
        result = await get_project(db_session, uuid.uuid4())
        assert result is None


@pytest.mark.asyncio
class TestCoreUpdateProject:
    async def test_update_partial(self, db_session: AsyncSession, workspace: Workspace):
        created = await create_project(
            db_session, workspace_id=workspace.id, name="orig", description="old"
        )
        updated = await update_project(db_session, created.id, description="new")
        assert updated.description == "new"
        assert updated.name == "orig"  # unchanged

    async def test_update_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await update_project(db_session, uuid.uuid4(), name="x")


@pytest.mark.asyncio
class TestCoreDeleteProject:
    async def test_delete_success(self, db_session: AsyncSession, workspace: Workspace):
        created = await create_project(db_session, workspace_id=workspace.id, name="del-me")
        await delete_project(db_session, created.id)
        assert await get_project(db_session, created.id) is None

    async def test_delete_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await delete_project(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Integration tests: API endpoints via AsyncClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateProjectEndpoint:
    async def test_create_201(self, client: AsyncClient, workspace_member: Workspace):
        resp = await client.post(
            "/api/projects",
            json={
                "workspace_id": str(workspace_member.id),
                "name": "api-project",
                "description": "desc",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "api-project"
        assert data["workspace_id"] == str(workspace_member.id)
        assert "id" in data
        assert "created_at" in data
        assert data["knowledge"] == {}

    async def test_create_missing_name_422(self, client: AsyncClient, workspace_member: Workspace):
        resp = await client.post(
            "/api/projects",
            json={"workspace_id": str(workspace_member.id)},
        )
        assert resp.status_code == 422

    async def test_create_bad_workspace_403(self, client: AsyncClient):
        # Non-member access returns 403 (permission check before existence check)
        resp = await client.post(
            "/api/projects",
            json={"workspace_id": str(uuid.uuid4()), "name": "orphan"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestListProjectsEndpoint:
    async def test_list_empty_200(self, client: AsyncClient):
        resp = await client.get("/api/projects")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_projects(self, client: AsyncClient, workspace_member: Workspace):
        await client.post(
            "/api/projects",
            json={"workspace_id": str(workspace_member.id), "name": "p1"},
        )
        await client.post(
            "/api/projects",
            json={"workspace_id": str(workspace_member.id), "name": "p2"},
        )
        resp = await client.get("/api/projects")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


@pytest.mark.asyncio
class TestGetProjectEndpoint:
    async def test_get_200(self, client: AsyncClient, workspace_member: Workspace):
        create_resp = await client.post(
            "/api/projects",
            json={"workspace_id": str(workspace_member.id), "name": "getme"},
        )
        project_id = create_resp.json()["id"]
        resp = await client.get(f"/api/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "getme"

    async def test_get_404(self, client: AsyncClient):
        resp = await client.get(f"/api/projects/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUpdateProjectEndpoint:
    async def test_patch_200(self, client: AsyncClient, workspace_member: Workspace):
        create_resp = await client.post(
            "/api/projects",
            json={
                "workspace_id": str(workspace_member.id),
                "name": "patchme",
                "description": "old",
            },
        )
        project_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/projects/{project_id}",
            json={"description": "updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "updated"
        assert resp.json()["name"] == "patchme"  # unchanged

    async def test_patch_404(self, client: AsyncClient):
        resp = await client.patch(
            f"/api/projects/{uuid.uuid4()}",
            json={"description": "nope"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDeleteProjectEndpoint:
    async def test_delete_204_then_404(self, client: AsyncClient, workspace_member: Workspace):
        create_resp = await client.post(
            "/api/projects",
            json={"workspace_id": str(workspace_member.id), "name": "deleteme"},
        )
        project_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/projects/{project_id}")
        assert resp.status_code == 204

        # Subsequent GET should return 404
        resp = await client.get(f"/api/projects/{project_id}")
        assert resp.status_code == 404

    async def test_delete_404(self, client: AsyncClient):
        resp = await client.delete(f"/api/projects/{uuid.uuid4()}")
        assert resp.status_code == 404
