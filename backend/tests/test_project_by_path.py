"""Tests for project-by-path core functions and API endpoints."""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.project import (
    get_or_create_project_by_path,
    get_project_by_path,
    normalize_path,
)
from codehive.db.models import Base, Project, Workspace

# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database (same pattern as test_projects.py)
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
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with auth disabled for by-path endpoints."""
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Unit tests: normalize_path
# ---------------------------------------------------------------------------


class TestNormalizePath:
    def test_strips_trailing_slash(self):
        assert normalize_path("/home/user/git/myapp/") == "/home/user/git/myapp"

    def test_absolute_path_unchanged(self):
        assert normalize_path("/home/user/git/myapp") == "/home/user/git/myapp"

    def test_double_slashes(self):
        result = normalize_path("/home//user///git/myapp")
        assert result == "/home/user/git/myapp"


# ---------------------------------------------------------------------------
# Unit tests: get_project_by_path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetProjectByPath:
    async def test_returns_none_for_unknown_path(self, db_session: AsyncSession):
        result = await get_project_by_path(db_session, "/nonexistent/path")
        assert result is None

    async def test_returns_project_for_known_path(
        self, db_session: AsyncSession, workspace: Workspace
    ):
        project = Project(
            workspace_id=workspace.id,
            name="myapp",
            path="/home/user/git/myapp",
            knowledge={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        found = await get_project_by_path(db_session, "/home/user/git/myapp")
        assert found is not None
        assert found.id == project.id
        assert found.name == "myapp"

    async def test_trailing_slash_matches(self, db_session: AsyncSession, workspace: Workspace):
        project = Project(
            workspace_id=workspace.id,
            name="myapp",
            path="/home/user/git/myapp",
            knowledge={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        found = await get_project_by_path(db_session, "/home/user/git/myapp/")
        assert found is not None
        assert found.id == project.id


# ---------------------------------------------------------------------------
# Unit tests: get_or_create_project_by_path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetOrCreateProjectByPath:
    async def test_creates_project_with_correct_name(
        self, db_session: AsyncSession, workspace: Workspace
    ):
        project, created = await get_or_create_project_by_path(
            db_session, "/home/user/git/myapp", workspace_id=workspace.id
        )
        assert created is True
        assert project.name == "myapp"
        assert project.path == "/home/user/git/myapp"
        assert project.id is not None

    async def test_idempotent_returns_existing(
        self, db_session: AsyncSession, workspace: Workspace
    ):
        project1, created1 = await get_or_create_project_by_path(
            db_session, "/home/user/git/myapp", workspace_id=workspace.id
        )
        project2, created2 = await get_or_create_project_by_path(
            db_session, "/home/user/git/myapp", workspace_id=workspace.id
        )
        assert created1 is True
        assert created2 is False
        assert project1.id == project2.id

    async def test_trailing_slash_idempotent(self, db_session: AsyncSession, workspace: Workspace):
        project1, created1 = await get_or_create_project_by_path(
            db_session, "/home/user/git/myapp", workspace_id=workspace.id
        )
        project2, created2 = await get_or_create_project_by_path(
            db_session, "/home/user/git/myapp/", workspace_id=workspace.id
        )
        assert created1 is True
        assert created2 is False
        assert project1.id == project2.id


# ---------------------------------------------------------------------------
# Integration tests: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetProjectByPathEndpoint:
    async def test_404_for_nonexistent(self, client: AsyncClient):
        resp = await client.get("/api/projects/by-path", params={"path": "/nonexistent"})
        assert resp.status_code == 404

    async def test_returns_created_project(self, client: AsyncClient, workspace: Workspace):
        # First create via POST
        resp = await client.post(
            "/api/projects/by-path",
            json={"path": "/tmp/testproject", "workspace_id": str(workspace.id)},
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        # Then GET should find it
        resp = await client.get("/api/projects/by-path", params={"path": "/tmp/testproject"})
        assert resp.status_code == 200
        assert resp.json()["id"] == project_id
        assert resp.json()["name"] == "testproject"


@pytest.mark.asyncio
class TestPostProjectByPathEndpoint:
    async def test_create_new_returns_201(self, client: AsyncClient, workspace: Workspace):
        resp = await client.post(
            "/api/projects/by-path",
            json={"path": "/tmp/testproject", "workspace_id": str(workspace.id)},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "testproject"
        assert data["path"] == "/tmp/testproject"
        assert "id" in data

    async def test_existing_returns_200_same_id(self, client: AsyncClient, workspace: Workspace):
        resp1 = await client.post(
            "/api/projects/by-path",
            json={"path": "/tmp/testproject", "workspace_id": str(workspace.id)},
        )
        assert resp1.status_code == 201
        project_id = resp1.json()["id"]

        resp2 = await client.post(
            "/api/projects/by-path",
            json={"path": "/tmp/testproject", "workspace_id": str(workspace.id)},
        )
        assert resp2.status_code == 200
        assert resp2.json()["id"] == project_id
