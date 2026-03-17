"""Tests for WebSocket JWT authentication (issue #72)."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.api.ws import verify_ws_token
from codehive.core.jwt import (
    TokenError,
    create_access_token,
    create_refresh_token,
)
from codehive.db.models import Base, Project, Session as SessionModel, Workspace

# All tests in this file require auth_enabled=True since they test WS auth behavior.
pytestmark = pytest.mark.usefixtures("_enable_auth")


@pytest.fixture(autouse=True)
def _enable_auth(monkeypatch):
    """Ensure auth is enabled for all tests in this module."""
    monkeypatch.setenv("CODEHIVE_AUTH_ENABLED", "true")


# ---------------------------------------------------------------------------
# Fixtures
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
async def session_id(db_session: AsyncSession) -> uuid.UUID:
    """Create a workspace, project, and session, returning the session ID."""
    ws = Workspace(
        id=uuid.uuid4(),
        name="test-ws",
        root_path="/tmp/test",
        settings={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(ws)
    await db_session.flush()

    proj = Project(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name="test-project",
        knowledge={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    await db_session.flush()

    sid = uuid.uuid4()
    sess = SessionModel(
        id=sid,
        project_id=proj.id,
        name="test-session",
        engine="mock",
        mode="auto",
        status="running",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(sess)
    await db_session.commit()
    return sid


@pytest.fixture
def app(db_session: AsyncSession):
    """Create app with DB override."""
    application = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    application.dependency_overrides[get_db] = _override_get_db
    return application


@pytest.fixture
def valid_token() -> str:
    return create_access_token(uuid.uuid4())


@pytest.fixture
def expired_token() -> str:
    return create_access_token(uuid.uuid4(), expires_delta=timedelta(seconds=-1))


@pytest.fixture
def refresh_token() -> str:
    return create_refresh_token(uuid.uuid4())


def _make_mock_redis():
    """Create a mock Redis whose listen() yields one test message then stops."""

    async def _listen():
        # Yield a real message so the handler sends it over the websocket
        yield {"type": "message", "data": b'{"event": "test"}'}

    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.aclose = AsyncMock()
    mock_pubsub.listen = _listen

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub
    mock_redis.close = AsyncMock()

    mock_redis_class = MagicMock()
    mock_redis_class.from_url.return_value = mock_redis
    return mock_redis_class


# ---------------------------------------------------------------------------
# Unit: verify_ws_token
# ---------------------------------------------------------------------------


class TestVerifyWsToken:
    def test_valid_access_token(self):
        uid = uuid.uuid4()
        token = create_access_token(uid)
        payload = verify_ws_token(token)
        assert payload["sub"] == str(uid)
        assert payload["type"] == "access"

    def test_expired_token_raises(self):
        token = create_access_token(uuid.uuid4(), expires_delta=timedelta(seconds=-1))
        with pytest.raises(TokenError):
            verify_ws_token(token)

    def test_refresh_token_raises(self):
        token = create_refresh_token(uuid.uuid4())
        with pytest.raises(TokenError, match="not an access token"):
            verify_ws_token(token)

    def test_garbage_token_raises(self):
        with pytest.raises(TokenError):
            verify_ws_token("garbage.not.a.jwt")

    def test_none_token_raises(self):
        with pytest.raises(TokenError, match="No token provided"):
            verify_ws_token(None)


# ---------------------------------------------------------------------------
# Integration: WebSocket auth via query parameter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWsAuthQueryParam:
    async def test_valid_token_accepted(self, app, session_id, valid_token):
        with patch("redis.asyncio.Redis", _make_mock_redis()):
            with TestClient(app) as client:
                with client.websocket_connect(
                    f"/api/sessions/{session_id}/ws?token={valid_token}"
                ) as ws:
                    # Connection accepted -- receive the mocked event
                    data = ws.receive_text()
                    assert "test" in data

    async def test_expired_token_rejected(self, app, session_id, expired_token):
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"/api/sessions/{session_id}/ws?token={expired_token}"
                ):
                    pass
            assert exc_info.value.code == 4001

    async def test_invalid_token_rejected(self, app, session_id):
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"/api/sessions/{session_id}/ws?token=invalid-garbage"
                ):
                    pass
            assert exc_info.value.code == 4001

    async def test_refresh_token_rejected(self, app, session_id, refresh_token):
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"/api/sessions/{session_id}/ws?token={refresh_token}"
                ):
                    pass
            assert exc_info.value.code == 4001


# ---------------------------------------------------------------------------
# Integration: WebSocket auth via first message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWsAuthFirstMessage:
    async def test_valid_auth_message_accepted(self, app, session_id, valid_token):
        with patch("redis.asyncio.Redis", _make_mock_redis()):
            with TestClient(app) as client:
                with client.websocket_connect(f"/api/sessions/{session_id}/ws") as ws:
                    ws.send_json({"type": "auth", "token": valid_token})
                    # Connection accepted -- receive the mocked event
                    data = ws.receive_text()
                    assert "test" in data

    async def test_invalid_token_in_message_rejected(self, app, session_id):
        with TestClient(app) as client:
            with client.websocket_connect(f"/api/sessions/{session_id}/ws") as ws:
                ws.send_json({"type": "auth", "token": "invalid-garbage"})
                # Server should close the connection with 4001
                msg = ws.receive()
                assert msg.get("code") == 4001

    async def test_non_auth_message_rejected(self, app, session_id):
        with TestClient(app) as client:
            with client.websocket_connect(f"/api/sessions/{session_id}/ws") as ws:
                ws.send_json({"type": "ping"})
                msg = ws.receive()
                assert msg.get("code") == 4001

    async def test_refresh_token_in_message_rejected(self, app, session_id, refresh_token):
        with TestClient(app) as client:
            with client.websocket_connect(f"/api/sessions/{session_id}/ws") as ws:
                ws.send_json({"type": "auth", "token": refresh_token})
                msg = ws.receive()
                assert msg.get("code") == 4001


# ---------------------------------------------------------------------------
# Integration: Interaction with existing behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWsAuthWithSession:
    async def test_valid_token_nonexistent_session_4004(self, app, valid_token):
        """Valid token but session does not exist -> 4004."""
        fake_session_id = uuid.uuid4()
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"/api/sessions/{fake_session_id}/ws?token={valid_token}"
                ):
                    pass
            assert exc_info.value.code == 4004

    async def test_valid_auth_message_nonexistent_session_4004(self, app, valid_token):
        """First-message auth with valid token but session does not exist -> 4004."""
        fake_session_id = uuid.uuid4()
        with TestClient(app) as client:
            with client.websocket_connect(f"/api/sessions/{fake_session_id}/ws") as ws:
                ws.send_json({"type": "auth", "token": valid_token})
                msg = ws.receive()
                assert msg.get("code") == 4004
