"""Tests for FCM push notifications: device registration API, FCM sending, dispatcher integration."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.config import Settings
from codehive.core.notifications import PushDispatcher
from codehive.db.models import Base, DeviceToken

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

        from sqlalchemy import Table

        Table(table.name, metadata, *columns)

    return metadata


@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite engine with tables."""
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    sqlite_metadata = _sqlite_compatible_metadata()

    async with engine.begin() as conn:
        await conn.run_sync(sqlite_metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(sqlite_metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    """Return a session factory."""
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with DB dependency override."""
    app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Register a test user and include auth headers
        resp = await c.post(
            "/api/auth/register",
            json={"email": "fcm@test.com", "username": "fcmuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides: object) -> Settings:
    defaults = {
        "vapid_private_key": "fake-private-key",
        "vapid_public_key": "fake-public-key",
        "vapid_mailto": "mailto:test@example.com",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def _make_pubsub_message(event_type: str, data: dict) -> dict:
    """Build a dict mimicking a Redis pub/sub pmessage."""
    return {
        "type": "pmessage",
        "pattern": b"session:*:events",
        "channel": b"session:sess-1:events",
        "data": json.dumps(
            {
                "id": "evt-1",
                "session_id": "sess-1",
                "type": event_type,
                "data": data,
                "created_at": "2026-03-16T12:00:00",
            }
        ).encode("utf-8"),
    }


# ---------------------------------------------------------------------------
# Device registration API tests
# ---------------------------------------------------------------------------


class TestDeviceRegistration:
    @pytest.mark.asyncio
    async def test_register_device_stores_in_db(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """POST /api/push/register-device with valid token and platform, verify 201 and persisted."""
        resp = await client.post(
            "/api/push/register-device",
            json={"token": "fcm-token-abc123", "platform": "android"},
        )
        assert resp.status_code == 201
        assert resp.json() == {"status": "registered"}

        from sqlalchemy import select

        result = await db_session.execute(select(DeviceToken))
        devices = list(result.scalars().all())
        assert len(devices) == 1
        assert devices[0].token == "fcm-token-abc123"
        assert devices[0].platform == "android"

    @pytest.mark.asyncio
    async def test_register_device_upserts_on_duplicate(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """POST /api/push/register-device with same token twice, verify only one record."""
        await client.post(
            "/api/push/register-device",
            json={"token": "fcm-token-dup", "platform": "android"},
        )
        resp = await client.post(
            "/api/push/register-device",
            json={"token": "fcm-token-dup", "platform": "ios", "device_id": "dev-1"},
        )
        assert resp.status_code == 201

        from sqlalchemy import select

        result = await db_session.execute(select(DeviceToken))
        devices = list(result.scalars().all())
        assert len(devices) == 1
        assert devices[0].platform == "ios"
        assert devices[0].device_id == "dev-1"

    @pytest.mark.asyncio
    async def test_unregister_device_removes_from_db(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """POST /api/push/unregister-device with existing token, verify 200 and removed."""
        await client.post(
            "/api/push/register-device",
            json={"token": "fcm-token-remove", "platform": "android"},
        )
        resp = await client.post(
            "/api/push/unregister-device",
            json={"token": "fcm-token-remove"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "unregistered"}

        from sqlalchemy import select

        result = await db_session.execute(select(DeviceToken))
        devices = list(result.scalars().all())
        assert len(devices) == 0

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_is_idempotent(self, client: AsyncClient):
        """POST /api/push/unregister-device with nonexistent token, verify 200."""
        resp = await client.post(
            "/api/push/unregister-device",
            json={"token": "fcm-token-nonexistent"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# FCM sending tests
# ---------------------------------------------------------------------------


class TestFCMSending:
    @pytest.mark.asyncio
    async def test_send_fcm_push_constructs_correct_message(self):
        """Mock firebase_admin.messaging.send, verify correct Message object."""
        import codehive.core.fcm as fcm_mod

        # Ensure the messaging submodule is imported so it can be patched
        import firebase_admin.messaging  # noqa: F401

        # Pretend Firebase is already initialized
        fcm_mod._initialized = True
        fcm_mod._firebase_app = MagicMock()

        try:
            with patch("firebase_admin.messaging.send", return_value="msg-id-123") as mock_send:
                result = fcm_mod.send_fcm_push(
                    token="device-token-123",
                    title="Test Title",
                    body="Test Body",
                    data={"event_type": "session.completed", "session_id": "s1"},
                )

                assert result is True
                mock_send.assert_called_once()
                msg_arg = mock_send.call_args[0][0]
                assert msg_arg.token == "device-token-123"
                assert msg_arg.notification.title == "Test Title"
                assert msg_arg.notification.body == "Test Body"
                assert msg_arg.data["event_type"] == "session.completed"
                assert msg_arg.data["session_id"] == "s1"
        finally:
            fcm_mod._initialized = False
            fcm_mod._firebase_app = None

    @pytest.mark.asyncio
    async def test_send_fcm_push_noop_when_not_configured(self):
        """Call send_fcm_push when Firebase is not initialized, verify no-op."""
        import codehive.core.fcm as fcm_mod

        fcm_mod._initialized = False
        fcm_mod._firebase_app = None

        try:
            with patch.dict("os.environ", {"FIREBASE_CREDENTIALS_JSON": ""}, clear=False):
                fcm_mod._initialized = False

                result = fcm_mod.send_fcm_push(
                    token="any-token",
                    title="Title",
                    body="Body",
                )
                assert result is False
        finally:
            fcm_mod._initialized = False
            fcm_mod._firebase_app = None


# ---------------------------------------------------------------------------
# Dispatcher FCM integration tests
# ---------------------------------------------------------------------------


class TestDispatcherFCMIntegration:
    @pytest.mark.asyncio
    async def test_approval_required_sends_fcm(self, session_factory):
        """Register device token, publish approval.required, verify FCM push sent."""
        settings = _make_settings()
        dispatcher = PushDispatcher(
            redis=AsyncMock(), session_factory=session_factory, settings=settings
        )

        async with session_factory() as db:
            db.add(DeviceToken(token="fcm-device-1", platform="android"))
            await db.commit()

        msg = _make_pubsub_message(
            "approval.required",
            {"session_name": "deploy", "action_description": "drop table"},
        )

        with (
            patch("codehive.core.notifications.webpush"),
            patch("codehive.core.notifications.send_fcm_push") as mock_fcm,
        ):
            await dispatcher._handle_message(msg)
            mock_fcm.assert_called_once()
            call_kwargs = mock_fcm.call_args
            assert call_kwargs.kwargs["title"] == "Approval Required"
            assert "deploy" in call_kwargs.kwargs["body"]
            assert call_kwargs.kwargs["data"]["event_type"] == "approval.required"

    @pytest.mark.asyncio
    async def test_session_failed_sends_fcm(self, session_factory):
        """Register device token, publish session.failed, verify FCM push sent."""
        settings = _make_settings()
        dispatcher = PushDispatcher(
            redis=AsyncMock(), session_factory=session_factory, settings=settings
        )

        async with session_factory() as db:
            db.add(DeviceToken(token="fcm-device-2", platform="android"))
            await db.commit()

        msg = _make_pubsub_message(
            "session.failed",
            {"session_name": "ci-build", "error": "OOM killed"},
        )

        with (
            patch("codehive.core.notifications.webpush"),
            patch("codehive.core.notifications.send_fcm_push") as mock_fcm,
        ):
            await dispatcher._handle_message(msg)
            mock_fcm.assert_called_once()
            assert "ci-build" in mock_fcm.call_args.kwargs["body"]

    @pytest.mark.asyncio
    async def test_non_notifiable_event_does_not_send_fcm(self, session_factory):
        """Register device token, publish file.changed (non-notifiable), verify FCM NOT called."""
        settings = _make_settings()
        dispatcher = PushDispatcher(
            redis=AsyncMock(), session_factory=session_factory, settings=settings
        )

        async with session_factory() as db:
            db.add(DeviceToken(token="fcm-device-3", platform="android"))
            await db.commit()

        msg = _make_pubsub_message("file.changed", {"path": "/src/main.py"})

        with (
            patch("codehive.core.notifications.webpush") as mock_wp,
            patch("codehive.core.notifications.send_fcm_push") as mock_fcm,
        ):
            await dispatcher._handle_message(msg)
            mock_wp.assert_not_called()
            mock_fcm.assert_not_called()

    @pytest.mark.asyncio
    async def test_stale_fcm_token_removed_on_error(self, session_factory):
        """Register device token, mock FCM send to raise Unregistered, verify token removed."""
        settings = _make_settings()
        dispatcher = PushDispatcher(
            redis=AsyncMock(), session_factory=session_factory, settings=settings
        )

        async with session_factory() as db:
            db.add(DeviceToken(token="fcm-stale-token", platform="android"))
            await db.commit()

        msg = _make_pubsub_message(
            "session.completed",
            {"session_name": "build", "summary": "All pass"},
        )

        # Create a mock exception that has UnregisteredError as its type name
        class UnregisteredError(Exception):
            pass

        with (
            patch("codehive.core.notifications.webpush"),
            patch(
                "codehive.core.notifications.send_fcm_push",
                side_effect=UnregisteredError("Token not registered"),
            ),
        ):
            await dispatcher._handle_message(msg)

        # Verify the stale token was removed
        async with session_factory() as db:
            from sqlalchemy import select

            result = await db.execute(select(DeviceToken))
            devices = list(result.scalars().all())
            assert len(devices) == 0
