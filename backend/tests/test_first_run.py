"""Tests for first-run setup: detection, seeding, idempotency, and integration."""

import contextlib
import os
from collections.abc import AsyncGenerator
from unittest import mock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.auth import verify_password
from codehive.core.first_run import is_first_run, print_credentials, seed_first_run
from codehive.db.models import Base, User

# All tests in this file require auth_enabled=True since they test first-run with auth.
pytestmark = pytest.mark.usefixtures("_enable_auth")


@pytest.fixture(autouse=True)
def _enable_auth(monkeypatch):
    """Ensure auth is enabled for all tests in this module."""
    monkeypatch.setenv("CODEHIVE_AUTH_ENABLED", "true")


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


@pytest.mark.asyncio
class TestFirstRunDetection:
    async def test_empty_db_returns_true(self, db_session: AsyncSession):
        assert await is_first_run(db_session) is True

    async def test_db_with_users_returns_false(self, db_session: AsyncSession):
        from codehive.core.auth import hash_password

        user = User(
            email="existing@test.com",
            username="existing",
            password_hash=hash_password("pass"),
        )
        db_session.add(user)
        await db_session.commit()

        assert await is_first_run(db_session) is False


@pytest.mark.asyncio
class TestSeeding:
    async def test_seed_with_env_vars(self, db_session: AsyncSession):
        with mock.patch.dict(
            os.environ,
            {"CODEHIVE_ADMIN_USERNAME": "testadmin", "CODEHIVE_ADMIN_PASSWORD": "testpass123"},
        ):
            result = await seed_first_run(db_session)

        assert result is not None
        assert result["username"] == "testadmin"
        assert result["password"] == "testpass123"

        user_result = await db_session.execute(select(User).where(User.username == "testadmin"))
        user = user_result.scalar_one()
        assert user.is_admin is True
        assert user.is_active is True
        assert verify_password("testpass123", user.password_hash) is True

    async def test_seed_without_env_vars(self, db_session: AsyncSession):
        with mock.patch.dict(
            os.environ,
            {"CODEHIVE_AUTH_ENABLED": "true"},
            clear=True,
        ):
            os.environ.pop("CODEHIVE_ADMIN_USERNAME", None)
            os.environ.pop("CODEHIVE_ADMIN_PASSWORD", None)
            result = await seed_first_run(db_session)

        assert result is not None
        assert result["username"] == "admin"
        assert len(result["password"]) > 0

        user_result = await db_session.execute(select(User).where(User.username == "admin"))
        user = user_result.scalar_one()
        assert verify_password(result["password"], user.password_hash) is True

    async def test_seed_no_op_when_auth_disabled(self, db_session: AsyncSession):
        with mock.patch.dict(os.environ, {"CODEHIVE_AUTH_ENABLED": "false"}, clear=True):
            result = await seed_first_run(db_session)
        assert result is None


@pytest.mark.asyncio
class TestIdempotency:
    async def test_seed_twice_only_creates_one_user(self, db_session: AsyncSession):
        with mock.patch.dict(
            os.environ,
            {"CODEHIVE_ADMIN_USERNAME": "admin", "CODEHIVE_ADMIN_PASSWORD": "pass"},
        ):
            first_result = await seed_first_run(db_session)
            second_result = await seed_first_run(db_session)

        assert first_result is not None
        assert second_result is None

        user_count = await db_session.execute(select(func.count()).select_from(User))
        assert user_count.scalar_one() == 1

    async def test_seed_skipped_with_existing_users(self, db_session: AsyncSession):
        from codehive.core.auth import hash_password

        user = User(
            email="pre@test.com",
            username="preexisting",
            password_hash=hash_password("pass"),
        )
        db_session.add(user)
        await db_session.commit()

        with mock.patch.dict(
            os.environ,
            {"CODEHIVE_ADMIN_USERNAME": "admin", "CODEHIVE_ADMIN_PASSWORD": "pass"},
        ):
            result = await seed_first_run(db_session)

        assert result is None


class TestPrintCredentials:
    def test_prints_credentials(self, capsys):
        creds = {"username": "admin", "password": "secret123", "email": "admin@codehive.local"}
        print_credentials(creds)
        captured = capsys.readouterr()
        assert "admin" in captured.out
        assert "secret123" in captured.out
        assert "admin@codehive.local" in captured.out

    def test_no_output_when_not_called(self, capsys):
        captured = capsys.readouterr()
        assert "password" not in captured.out


@pytest_asyncio.fixture
async def first_run_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    with mock.patch.dict(
        os.environ,
        {"CODEHIVE_ADMIN_USERNAME": "admin", "CODEHIVE_ADMIN_PASSWORD": "adminpass123"},
    ):
        result = await seed_first_run(db_session)
        assert result is not None

    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    @contextlib.asynccontextmanager
    async def _noop_lifespan(app):  # type: ignore[no-untyped-def]
        yield

    app.router.lifespan_context = _noop_lifespan

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestIntegrationStartup:
    async def test_health_after_first_run(self, first_run_client: AsyncClient):
        resp = await first_run_client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_login_with_admin_credentials(self, first_run_client: AsyncClient):
        resp = await first_run_client.post(
            "/api/auth/login",
            json={"email": "admin@codehive.local", "password": "adminpass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
