"""Tests for User model, password hashing, JWT tokens, and auth endpoints."""

import uuid
from collections.abc import AsyncGenerator
from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.auth import hash_password, verify_password
from codehive.core.jwt import TokenError, create_access_token, create_refresh_token, decode_token
from codehive.db.models import Base

# All tests in this file require auth_enabled=True since they test auth behavior.
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
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _register_user(
    client: AsyncClient,
    email: str = "test@example.com",
    username: str = "testuser",
    password: str = "secret123",
) -> dict:
    """Register a user and return the response JSON."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Unit: Password hashing
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        h = hash_password("secret")
        assert h != "secret"
        assert isinstance(h, str)

    def test_verify_correct_password(self):
        h = hash_password("secret")
        assert verify_password("secret", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("secret")
        assert verify_password("wrong", h) is False

    def test_different_salts(self):
        h1 = hash_password("secret")
        h2 = hash_password("secret")
        assert h1 != h2


# ---------------------------------------------------------------------------
# Unit: JWT tokens
# ---------------------------------------------------------------------------


class TestJWT:
    def test_access_token_roundtrip(self):
        uid = uuid.uuid4()
        token = create_access_token(uid)
        payload = decode_token(token)
        assert payload["sub"] == str(uid)
        assert payload["type"] == "access"

    def test_refresh_token_roundtrip(self):
        uid = uuid.uuid4()
        token = create_refresh_token(uid)
        payload = decode_token(token)
        assert payload["sub"] == str(uid)
        assert payload["type"] == "refresh"

    def test_expired_access_token_raises(self):
        uid = uuid.uuid4()
        token = create_access_token(uid, expires_delta=timedelta(seconds=-1))
        with pytest.raises(TokenError):
            decode_token(token)

    def test_garbage_token_raises(self):
        with pytest.raises(TokenError):
            decode_token("garbage")

    def test_refresh_lives_longer_than_access(self):
        uid = uuid.uuid4()
        access = create_access_token(uid)
        refresh = create_refresh_token(uid)
        access_payload = decode_token(access)
        refresh_payload = decode_token(refresh)
        assert refresh_payload["exp"] > access_payload["exp"]


# ---------------------------------------------------------------------------
# Integration: Register endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        data = await _register_user(client)
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_token_is_valid(self, client: AsyncClient):
        data = await _register_user(client)
        payload = decode_token(data["access_token"])
        assert payload["type"] == "access"
        assert "sub" in payload

    async def test_register_duplicate_email_409(self, client: AsyncClient):
        await _register_user(client, email="dup@example.com", username="user1")
        resp = await client.post(
            "/api/auth/register",
            json={"email": "dup@example.com", "username": "user2", "password": "pass"},
        )
        assert resp.status_code == 409

    async def test_register_duplicate_username_409(self, client: AsyncClient):
        await _register_user(client, email="a@example.com", username="dupuser")
        resp = await client.post(
            "/api/auth/register",
            json={"email": "b@example.com", "username": "dupuser", "password": "pass"},
        )
        assert resp.status_code == 409

    async def test_register_missing_fields_422(self, client: AsyncClient):
        resp = await client.post("/api/auth/register", json={"email": "x@x.com"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Integration: Login endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client: AsyncClient):
        await _register_user(client, email="login@example.com", password="mypass")
        resp = await client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": "mypass"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_wrong_password_401(self, client: AsyncClient):
        await _register_user(client, email="login2@example.com", password="correct")
        resp = await client.post(
            "/api/auth/login",
            json={"email": "login2@example.com", "password": "wrong"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_email_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "anything"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Integration: Refresh endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRefresh:
    async def test_refresh_success(self, client: AsyncClient):
        tokens = await _register_user(client)
        resp = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_with_access_token_401(self, client: AsyncClient):
        tokens = await _register_user(client)
        resp = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens["access_token"]},
        )
        assert resp.status_code == 401

    async def test_refresh_with_invalid_token_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid-garbage"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Integration: Me endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMe:
    async def test_me_success(self, client: AsyncClient):
        tokens = await _register_user(client, email="me@example.com", username="meuser")
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@example.com"
        assert data["username"] == "meuser"
        assert data["is_active"] is True
        assert data["is_admin"] is False
        assert "id" in data
        assert "created_at" in data
        assert "password_hash" not in data

    async def test_me_no_auth_401(self, client: AsyncClient):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_me_invalid_token_401(self, client: AsyncClient):
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Integration: Protected routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestProtectedRoutes:
    async def test_projects_without_token_401(self, client: AsyncClient):
        resp = await client.get("/api/projects")
        assert resp.status_code == 401

    async def test_projects_with_token_200(self, client: AsyncClient):
        tokens = await _register_user(client)
        resp = await client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200

    async def test_health_no_auth_200(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
