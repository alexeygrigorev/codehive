"""Tests for Workspace CRUD API endpoints and core logic."""

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
from codehive.core.workspace import (
    WorkspaceDuplicateNameError,
    WorkspaceHasDependentsError,
    WorkspaceNotFoundError,
    create_workspace,
    delete_workspace,
    get_workspace,
    list_workspace_projects,
    list_workspaces,
    update_workspace,
)
from codehive.db.models import Base, Project

# All tests in this file require auth_enabled=True since they test workspace/auth behavior.
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
# Unit tests: Core workspace operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreCreateWorkspace:
    async def test_create_workspace_success(self, db_session: AsyncSession):
        ws = await create_workspace(db_session, name="my-workspace", root_path="/tmp/ws")
        assert ws.id is not None
        assert isinstance(ws.id, uuid.UUID)
        assert ws.name == "my-workspace"
        assert ws.root_path == "/tmp/ws"
        assert ws.settings == {}
        assert ws.created_at is not None

    async def test_create_workspace_with_settings(self, db_session: AsyncSession):
        ws = await create_workspace(
            db_session,
            name="ws-settings",
            root_path="/tmp/ws",
            settings={"key": "value"},
        )
        assert ws.settings == {"key": "value"}

    async def test_create_workspace_duplicate_name(self, db_session: AsyncSession):
        await create_workspace(db_session, name="dupe", root_path="/tmp/a")
        with pytest.raises(WorkspaceDuplicateNameError):
            await create_workspace(db_session, name="dupe", root_path="/tmp/b")


@pytest.mark.asyncio
class TestCoreListWorkspaces:
    async def test_list_empty(self, db_session: AsyncSession):
        workspaces = await list_workspaces(db_session)
        assert workspaces == []

    async def test_list_multiple(self, db_session: AsyncSession):
        await create_workspace(db_session, name="ws1", root_path="/tmp/1")
        await create_workspace(db_session, name="ws2", root_path="/tmp/2")
        workspaces = await list_workspaces(db_session)
        assert len(workspaces) == 2


@pytest.mark.asyncio
class TestCoreGetWorkspace:
    async def test_get_existing(self, db_session: AsyncSession):
        created = await create_workspace(db_session, name="getme", root_path="/tmp/g")
        found = await get_workspace(db_session, created.id)
        assert found is not None
        assert found.id == created.id

    async def test_get_nonexistent(self, db_session: AsyncSession):
        result = await get_workspace(db_session, uuid.uuid4())
        assert result is None


@pytest.mark.asyncio
class TestCoreUpdateWorkspace:
    async def test_update_name(self, db_session: AsyncSession):
        created = await create_workspace(db_session, name="orig", root_path="/tmp/u")
        updated = await update_workspace(db_session, created.id, name="renamed")
        assert updated.name == "renamed"
        assert updated.root_path == "/tmp/u"  # unchanged

    async def test_update_settings(self, db_session: AsyncSession):
        created = await create_workspace(
            db_session, name="settws", root_path="/tmp/s", settings={"a": 1}
        )
        updated = await update_workspace(db_session, created.id, settings={"b": 2})
        assert updated.settings == {"b": 2}

    async def test_update_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(WorkspaceNotFoundError):
            await update_workspace(db_session, uuid.uuid4(), name="x")


@pytest.mark.asyncio
class TestCoreDeleteWorkspace:
    async def test_delete_success(self, db_session: AsyncSession):
        created = await create_workspace(db_session, name="del-me", root_path="/tmp/d")
        await delete_workspace(db_session, created.id)
        assert await get_workspace(db_session, created.id) is None

    async def test_delete_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(WorkspaceNotFoundError):
            await delete_workspace(db_session, uuid.uuid4())

    async def test_delete_with_projects(self, db_session: AsyncSession):
        ws = await create_workspace(db_session, name="has-projects", root_path="/tmp/hp")
        project = Project(
            workspace_id=ws.id,
            name="child-project",
            knowledge={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(project)
        await db_session.commit()

        with pytest.raises(WorkspaceHasDependentsError):
            await delete_workspace(db_session, ws.id)


@pytest.mark.asyncio
class TestCoreListWorkspaceProjects:
    async def test_list_projects(self, db_session: AsyncSession):
        ws = await create_workspace(db_session, name="ws-proj", root_path="/tmp/wp")
        p = Project(
            workspace_id=ws.id,
            name="proj1",
            knowledge={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(p)
        await db_session.commit()

        projects = await list_workspace_projects(db_session, ws.id)
        assert len(projects) == 1
        assert projects[0].name == "proj1"

    async def test_list_projects_nonexistent_workspace(self, db_session: AsyncSession):
        with pytest.raises(WorkspaceNotFoundError):
            await list_workspace_projects(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Integration tests: API endpoints via AsyncClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateWorkspaceEndpoint:
    async def test_create_201(self, client: AsyncClient):
        resp = await client.post(
            "/api/workspaces",
            json={"name": "api-ws", "root_path": "/tmp/api"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "api-ws"
        assert data["root_path"] == "/tmp/api"
        assert data["settings"] == {}
        assert "id" in data
        assert "created_at" in data

    async def test_create_with_settings_201(self, client: AsyncClient):
        resp = await client.post(
            "/api/workspaces",
            json={
                "name": "ws-set",
                "root_path": "/tmp/s",
                "settings": {"integration": "github"},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["settings"] == {"integration": "github"}

    async def test_create_missing_name_422(self, client: AsyncClient):
        resp = await client.post(
            "/api/workspaces",
            json={"root_path": "/tmp/no-name"},
        )
        assert resp.status_code == 422

    async def test_create_missing_root_path_422(self, client: AsyncClient):
        resp = await client.post(
            "/api/workspaces",
            json={"name": "no-root"},
        )
        assert resp.status_code == 422

    async def test_create_duplicate_name_409(self, client: AsyncClient):
        await client.post(
            "/api/workspaces",
            json={"name": "dup-ws", "root_path": "/tmp/a"},
        )
        resp = await client.post(
            "/api/workspaces",
            json={"name": "dup-ws", "root_path": "/tmp/b"},
        )
        assert resp.status_code == 409


@pytest.mark.asyncio
class TestListWorkspacesEndpoint:
    async def test_list_empty_200(self, client: AsyncClient):
        resp = await client.get("/api/workspaces")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_workspaces(self, client: AsyncClient):
        await client.post(
            "/api/workspaces",
            json={"name": "ws1", "root_path": "/tmp/1"},
        )
        await client.post(
            "/api/workspaces",
            json={"name": "ws2", "root_path": "/tmp/2"},
        )
        resp = await client.get("/api/workspaces")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


@pytest.mark.asyncio
class TestGetWorkspaceEndpoint:
    async def test_get_200(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/workspaces",
            json={"name": "getme", "root_path": "/tmp/g", "settings": {"k": "v"}},
        )
        ws_id = create_resp.json()["id"]
        resp = await client.get(f"/api/workspaces/{ws_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "getme"
        assert data["settings"] == {"k": "v"}

    async def test_get_nonexistent_403(self, client: AsyncClient):
        # Non-member access returns 403 (permission check before existence check)
        resp = await client.get(f"/api/workspaces/{uuid.uuid4()}")
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestUpdateWorkspaceEndpoint:
    async def test_patch_name_200(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/workspaces",
            json={"name": "patchme", "root_path": "/tmp/p"},
        )
        ws_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/workspaces/{ws_id}",
            json={"name": "updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "updated"
        assert resp.json()["root_path"] == "/tmp/p"  # unchanged

    async def test_patch_settings_200(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/workspaces",
            json={"name": "set-ws", "root_path": "/tmp/s"},
        )
        ws_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/workspaces/{ws_id}",
            json={"settings": {"key": "value"}},
        )
        assert resp.status_code == 200
        assert resp.json()["settings"] == {"key": "value"}

    async def test_patch_nonexistent_403(self, client: AsyncClient):
        # Non-member access returns 403 (permission check before existence check)
        resp = await client.patch(
            f"/api/workspaces/{uuid.uuid4()}",
            json={"name": "nope"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestDeleteWorkspaceEndpoint:
    async def test_delete_204_then_403(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/workspaces",
            json={"name": "deleteme", "root_path": "/tmp/d"},
        )
        ws_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/workspaces/{ws_id}")
        assert resp.status_code == 204

        # After deletion, user is no longer a member so gets 403
        resp = await client.get(f"/api/workspaces/{ws_id}")
        assert resp.status_code == 403

    async def test_delete_nonexistent_403(self, client: AsyncClient):
        # Non-member access returns 403 (permission check before existence check)
        resp = await client.delete(f"/api/workspaces/{uuid.uuid4()}")
        assert resp.status_code == 403

    async def test_delete_with_projects_409(self, client: AsyncClient):
        # Create workspace
        ws_resp = await client.post(
            "/api/workspaces",
            json={"name": "ws-with-proj", "root_path": "/tmp/wp"},
        )
        ws_id = ws_resp.json()["id"]

        # Create project in that workspace
        await client.post(
            "/api/projects",
            json={"workspace_id": ws_id, "name": "child-proj"},
        )

        # Try to delete workspace
        resp = await client.delete(f"/api/workspaces/{ws_id}")
        assert resp.status_code == 409


@pytest.mark.asyncio
class TestListWorkspaceProjectsEndpoint:
    async def test_list_projects_200(self, client: AsyncClient):
        ws_resp = await client.post(
            "/api/workspaces",
            json={"name": "proj-ws", "root_path": "/tmp/pp"},
        )
        ws_id = ws_resp.json()["id"]

        await client.post(
            "/api/projects",
            json={"workspace_id": ws_id, "name": "p1"},
        )
        await client.post(
            "/api/projects",
            json={"workspace_id": ws_id, "name": "p2"},
        )

        resp = await client.get(f"/api/workspaces/{ws_id}/projects")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_list_projects_empty_200(self, client: AsyncClient):
        ws_resp = await client.post(
            "/api/workspaces",
            json={"name": "empty-ws", "root_path": "/tmp/e"},
        )
        ws_id = ws_resp.json()["id"]

        resp = await client.get(f"/api/workspaces/{ws_id}/projects")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_projects_nonexistent_403(self, client: AsyncClient):
        # Non-member access returns 403 (permission check before existence check)
        resp = await client.get(f"/api/workspaces/{uuid.uuid4()}/projects")
        assert resp.status_code == 403
