"""End-to-end integration test: full user journey against the real FastAPI app.

Exercises the vertical slice: register -> login -> create workspace -> create
project -> create session -> send message.  Only the engine layer (LLM call)
is mocked; everything else -- routing, auth, permissions, DB -- is real.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.db.models import Base

# E2E tests exercise the full auth flow and require auth_enabled=True.
pytestmark = pytest.mark.usefixtures("_enable_auth")


@pytest.fixture(autouse=True)
def _enable_auth(monkeypatch):
    """Ensure auth is enabled for all tests in this module."""
    monkeypatch.setenv("CODEHIVE_AUTH_ENABLED", "true")


# ---------------------------------------------------------------------------
# SQLite-compatible metadata helper (same pattern as test_auth.py)
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _test_engine():
    """Create an async SQLite engine with all tables."""
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
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(_test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session bound to the in-memory SQLite engine."""
    factory = async_sessionmaker(_test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Build httpx.AsyncClient against the real FastAPI app with DB override."""
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register(
    client: AsyncClient,
    email: str = "e2e@example.com",
    username: str = "e2euser",
    password: str = "supersecret",
) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _auth_headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _make_fake_engine():
    """Return a mock engine whose send_message yields deterministic events."""

    async def _fake_send_message(session_id: uuid.UUID, content: str, **kwargs: Any):
        yield {"type": "message.created", "data": {"content": "Hello from mock"}}

    engine = AsyncMock()
    engine.send_message = _fake_send_message
    return engine


# ---------------------------------------------------------------------------
# E2E: Full user journey (happy path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestE2EHappyPath:
    """Register -> login -> workspace -> project -> session -> message."""

    async def test_register(self, client: AsyncClient):
        tokens = await _register(client)
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"

    async def test_login(self, client: AsyncClient):
        await _register(client, email="login@e2e.com", username="loginuser", password="pass123")
        resp = await client.post(
            "/api/auth/login",
            json={"email": "login@e2e.com", "password": "pass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_get_current_user(self, client: AsyncClient):
        tokens = await _register(client, email="me@e2e.com", username="meuser")
        resp = await client.get("/api/auth/me", headers=_auth_headers(tokens))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@e2e.com"
        assert data["username"] == "meuser"

    async def test_full_journey(self, client: AsyncClient):
        """Complete vertical slice: register through sending a message."""
        # 1. Register
        tokens = await _register(client)
        headers = _auth_headers(tokens)

        # 2. Login with same credentials
        resp = await client.post(
            "/api/auth/login",
            json={"email": "e2e@example.com", "password": "supersecret"},
        )
        assert resp.status_code == 200

        # 3. Create workspace
        resp = await client.post(
            "/api/workspaces",
            json={"name": "E2E Workspace", "root_path": "/tmp/e2e"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        workspace = resp.json()
        workspace_id = workspace["id"]
        assert workspace["name"] == "E2E Workspace"

        # 4. Create project
        resp = await client.post(
            "/api/projects",
            json={"workspace_id": workspace_id, "name": "E2E Project"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        project = resp.json()
        project_id = project["id"]
        assert project["workspace_id"] == workspace_id
        assert project["name"] == "E2E Project"

        # 5. Create session
        resp = await client.post(
            f"/api/projects/{project_id}/sessions",
            json={"name": "E2E Session", "engine": "native", "mode": "execution"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        session = resp.json()
        session_id = session["id"]
        assert session["status"] == "idle"

        # 6. Send message (mock the engine)
        fake_engine = _make_fake_engine()
        with patch(
            "codehive.api.routes.sessions._build_engine",
            return_value=fake_engine,
        ):
            resp = await client.post(
                f"/api/sessions/{session_id}/messages",
                json={"content": "Hello, agent!"},
                headers=headers,
            )
        assert resp.status_code == 200, resp.text
        events = resp.json()
        assert isinstance(events, list)
        assert len(events) >= 1
        assert events[0]["type"] == "message.created"
        assert events[0]["data"]["content"] == "Hello from mock"


# ---------------------------------------------------------------------------
# E2E: Auth rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestE2EAuthRejection:
    """Protected endpoints must reject unauthenticated requests."""

    async def test_workspaces_no_auth_401(self, client: AsyncClient):
        resp = await client.get("/api/workspaces")
        assert resp.status_code == 401

    async def test_workspaces_invalid_token_401(self, client: AsyncClient):
        resp = await client.get(
            "/api/workspaces",
            headers={"Authorization": "Bearer invalid-token-value"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# E2E: Entity relationships
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestE2EEntityRelationships:
    """Verify parent-child entity lookups work end-to-end."""

    async def test_workspace_projects_and_project_sessions(self, client: AsyncClient):
        """Create workspace -> project -> session, then list through parents."""
        tokens = await _register(client, email="rel@e2e.com", username="reluser")
        headers = _auth_headers(tokens)

        # Workspace
        resp = await client.post(
            "/api/workspaces",
            json={"name": "Rel Workspace", "root_path": "/tmp/rel"},
            headers=headers,
        )
        assert resp.status_code == 201
        workspace_id = resp.json()["id"]

        # Project
        resp = await client.post(
            "/api/projects",
            json={"workspace_id": workspace_id, "name": "Rel Project"},
            headers=headers,
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        # Session
        resp = await client.post(
            f"/api/projects/{project_id}/sessions",
            json={"name": "Rel Session", "engine": "native", "mode": "execution"},
            headers=headers,
        )
        assert resp.status_code == 201

        # List projects under workspace
        resp = await client.get(
            f"/api/workspaces/{workspace_id}/projects",
            headers=headers,
        )
        assert resp.status_code == 200
        projects = resp.json()
        assert len(projects) >= 1
        assert any(p["id"] == project_id for p in projects)

        # List sessions under project
        resp = await client.get(
            f"/api/projects/{project_id}/sessions",
            headers=headers,
        )
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) >= 1
        assert sessions[0]["status"] == "idle"
