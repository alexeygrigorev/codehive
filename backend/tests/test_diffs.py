"""Tests for GET /api/sessions/{session_id}/diffs endpoint."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, MetaData, Table, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.api.routes.sessions import get_diff_service
from codehive.db.models import Base, Project, Workspace
from codehive.db.models import Session as SessionModel
from codehive.execution.diff import DiffService

# ---------------------------------------------------------------------------
# Fixtures
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
        Table(table.name, metadata, *columns)
    return metadata


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
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
async def session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="test-session",
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
async def diff_service() -> DiffService:
    return DiffService()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, diff_service: DiffService
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_diff_service] = lambda: diff_service

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
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetSessionDiffsEndpoint:
    async def test_diffs_no_changes_returns_empty_files(
        self,
        client: AsyncClient,
        session: SessionModel,
    ):
        """GET /api/sessions/{id}/diffs with no tracked changes returns empty files array."""
        resp = await client.get(f"/api/sessions/{session.id}/diffs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == str(session.id)
        assert data["files"] == []

    async def test_diffs_with_tracked_changes(
        self,
        client: AsyncClient,
        session: SessionModel,
        diff_service: DiffService,
    ):
        """GET /api/sessions/{id}/diffs with tracked changes returns correct entries."""
        diff_text = (
            "--- a/src/auth.py\n"
            "+++ b/src/auth.py\n"
            "@@ -1,3 +1,5 @@\n"
            " import os\n"
            "+import sys\n"
            "+import json\n"
            " \n"
            "-old_line\n"
            " def main():\n"
        )
        diff_service.track_change(str(session.id), "src/auth.py", diff_text)

        resp = await client.get(f"/api/sessions/{session.id}/diffs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == str(session.id)
        assert len(data["files"]) == 1

        file_entry = data["files"][0]
        assert file_entry["path"] == "src/auth.py"
        assert file_entry["diff_text"] == diff_text
        assert file_entry["additions"] == 2
        assert file_entry["deletions"] == 1

    async def test_diffs_nonexistent_session_returns_404(
        self,
        client: AsyncClient,
    ):
        """GET /api/sessions/{nonexistent}/diffs returns 404."""
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/diffs")
        assert resp.status_code == 404

    async def test_diffs_multiple_files(
        self,
        client: AsyncClient,
        session: SessionModel,
        diff_service: DiffService,
    ):
        """Multiple tracked files are all returned."""
        diff1 = "--- a/a.py\n+++ b/a.py\n@@ -1 +1,2 @@\n line\n+added\n"
        diff2 = "--- a/b.py\n+++ b/b.py\n@@ -1,2 +1 @@\n line\n-removed\n"
        diff_service.track_change(str(session.id), "a.py", diff1)
        diff_service.track_change(str(session.id), "b.py", diff2)

        resp = await client.get(f"/api/sessions/{session.id}/diffs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["files"]) == 2
        paths = {f["path"] for f in data["files"]}
        assert paths == {"a.py", "b.py"}
