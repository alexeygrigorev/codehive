"""Tests for auth bypass when auth_enabled=False (issue #88a)."""

import os
import uuid
from collections.abc import AsyncGenerator
from unittest import mock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, MetaData, Table, event, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.db.models import Base, Workspace

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


def _create_app_with_auth(auth_enabled: bool):
    """Create app with the given auth_enabled setting."""
    with mock.patch.dict(
        os.environ,
        {"CODEHIVE_AUTH_ENABLED": str(auth_enabled).lower()},
    ):
        from codehive.api.app import create_app

        return create_app()


@pytest_asyncio.fixture
async def client_auth_disabled(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Client with auth_enabled=False."""
    with mock.patch.dict(
        os.environ,
        {"CODEHIVE_AUTH_ENABLED": "false"},
    ):
        from codehive.api.app import create_app
        from codehive.api.deps import get_db

        app = create_app()

        async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        app.dependency_overrides[get_db] = _override_get_db

        import contextlib

        @contextlib.asynccontextmanager
        async def _noop_lifespan(app):
            yield

        app.router.lifespan_context = _noop_lifespan

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture
async def client_auth_enabled(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Client with auth_enabled=True."""
    with mock.patch.dict(
        os.environ,
        {"CODEHIVE_AUTH_ENABLED": "true"},
    ):
        from codehive.api.app import create_app
        from codehive.api.deps import get_db

        app = create_app()

        async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        app.dependency_overrides[get_db] = _override_get_db

        import contextlib

        @contextlib.asynccontextmanager
        async def _noop_lifespan(app):
            yield

        app.router.lifespan_context = _noop_lifespan

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Unit: get_current_user bypass
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetCurrentUserBypass:
    async def test_auth_disabled_returns_anonymous(self, db_session: AsyncSession):
        """With auth_enabled=False, get_current_user returns AnonymousUser."""
        with mock.patch.dict(os.environ, {"CODEHIVE_AUTH_ENABLED": "false"}):
            from codehive.api.deps import AnonymousUser, get_current_user

            result = await get_current_user(credentials=None, db=db_session)
            assert isinstance(result, AnonymousUser)
            assert result.id is not None

    async def test_auth_enabled_raises_401(self, db_session: AsyncSession):
        """With auth_enabled=True, get_current_user raises 401 without token."""
        with mock.patch.dict(os.environ, {"CODEHIVE_AUTH_ENABLED": "true"}):
            from fastapi import HTTPException

            from codehive.api.deps import get_current_user

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=None, db=db_session)
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Unit: Permission bypass
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPermissionBypass:
    async def test_check_workspace_access_bypassed(self, db_session: AsyncSession):
        """With auth_enabled=False, check_workspace_access returns None."""
        with mock.patch.dict(os.environ, {"CODEHIVE_AUTH_ENABLED": "false"}):
            from codehive.core.permissions import check_workspace_access

            result = await check_workspace_access(db_session, uuid.uuid4(), uuid.uuid4(), "owner")
            assert result is None

    async def test_check_project_access_bypassed(self, db_session: AsyncSession):
        """With auth_enabled=False, check_project_access returns None."""
        with mock.patch.dict(os.environ, {"CODEHIVE_AUTH_ENABLED": "false"}):
            from codehive.core.permissions import check_project_access

            result = await check_project_access(db_session, uuid.uuid4(), uuid.uuid4(), "owner")
            assert result is None


# ---------------------------------------------------------------------------
# Unit: Auth config endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAuthConfigEndpoint:
    async def test_auth_config_returns_false(self, client_auth_disabled: AsyncClient):
        resp = await client_auth_disabled.get("/api/auth/config")
        assert resp.status_code == 200
        assert resp.json() == {"auth_enabled": False}

    async def test_auth_config_returns_true(self, client_auth_enabled: AsyncClient):
        resp = await client_auth_enabled.get("/api/auth/config")
        assert resp.status_code == 200
        assert resp.json() == {"auth_enabled": True}


# ---------------------------------------------------------------------------
# Integration: API routes without auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestApiWithoutAuth:
    async def test_projects_200_without_token(self, client_auth_disabled: AsyncClient):
        """GET /api/projects returns 200 without Authorization header."""
        resp = await client_auth_disabled.get("/api/projects")
        assert resp.status_code == 200

    async def test_health_200(self, client_auth_disabled: AsyncClient):
        """Health endpoint still works."""
        resp = await client_auth_disabled.get("/api/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Integration: API with auth re-enabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestApiWithAuthEnabled:
    async def test_projects_401_without_token(self, client_auth_enabled: AsyncClient):
        """GET /api/projects returns 401 without Authorization header when auth enabled."""
        resp = await client_auth_enabled.get("/api/projects")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Unit: first_run with auth disabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFirstRunAuthDisabled:
    async def test_seed_creates_workspace_no_user(self, db_session: AsyncSession):
        """With auth_enabled=False, seed creates workspace but no user."""
        with mock.patch.dict(os.environ, {"CODEHIVE_AUTH_ENABLED": "false"}):
            from codehive.core.first_run import seed_first_run
            from codehive.db.models import User

            result = await seed_first_run(db_session)
            assert result is None

            # Workspace should be created
            ws_result = await db_session.execute(
                select(Workspace).where(Workspace.name == "Default")
            )
            assert ws_result.scalar_one_or_none() is not None

            # No user should be created
            user_count = await db_session.execute(select(func.count()).select_from(User))
            assert user_count.scalar_one() == 0

    async def test_seed_idempotent_auth_disabled(self, db_session: AsyncSession):
        """Running seed twice with auth_enabled=False doesn't create duplicate workspaces."""
        with mock.patch.dict(os.environ, {"CODEHIVE_AUTH_ENABLED": "false"}):
            from codehive.core.first_run import seed_first_run

            await seed_first_run(db_session)
            await seed_first_run(db_session)

            ws_count = await db_session.execute(select(func.count()).select_from(Workspace))
            assert ws_count.scalar_one() == 1

    async def test_seed_with_auth_enabled_creates_user(self, db_session: AsyncSession):
        """With auth_enabled=True, seed creates user as before."""
        with mock.patch.dict(
            os.environ,
            {
                "CODEHIVE_AUTH_ENABLED": "true",
                "CODEHIVE_ADMIN_USERNAME": "admin",
                "CODEHIVE_ADMIN_PASSWORD": "testpass",
            },
        ):
            from codehive.core.first_run import seed_first_run
            from codehive.db.models import User

            result = await seed_first_run(db_session)
            assert result is not None
            assert result["username"] == "admin"

            user_count = await db_session.execute(select(func.count()).select_from(User))
            assert user_count.scalar_one() == 1
