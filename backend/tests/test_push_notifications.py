"""Tests for push notification endpoints and PushDispatcher."""

from __future__ import annotations

import asyncio
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
from codehive.core.notifications import PushDispatcher, _build_payload
from codehive.db.models import Base, PushSubscription

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
                "created_at": "2026-03-15T12:00:00",
            }
        ).encode("utf-8"),
    }


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestSubscribeEndpoint:
    @pytest.mark.asyncio
    async def test_subscribe_stores_in_db(self, client: AsyncClient, db_session: AsyncSession):
        """Store a push subscription via POST /api/push/subscribe, verify it persists."""
        resp = await client.post(
            "/api/push/subscribe",
            json={
                "endpoint": "https://push.example.com/sub1",
                "keys": {"p256dh": "key-p256dh", "auth": "key-auth"},
            },
        )
        assert resp.status_code == 201
        assert resp.json() == {"status": "subscribed"}

        from sqlalchemy import select

        result = await db_session.execute(select(PushSubscription))
        subs = list(result.scalars().all())
        assert len(subs) == 1
        assert subs[0].endpoint == "https://push.example.com/sub1"
        assert subs[0].p256dh == "key-p256dh"
        assert subs[0].auth == "key-auth"

    @pytest.mark.asyncio
    async def test_subscribe_upserts_on_duplicate(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Store a duplicate subscription (same endpoint), verify it upserts."""
        await client.post(
            "/api/push/subscribe",
            json={
                "endpoint": "https://push.example.com/sub1",
                "keys": {"p256dh": "old-key", "auth": "old-auth"},
            },
        )
        resp = await client.post(
            "/api/push/subscribe",
            json={
                "endpoint": "https://push.example.com/sub1",
                "keys": {"p256dh": "new-key", "auth": "new-auth"},
            },
        )
        assert resp.status_code == 201

        from sqlalchemy import select

        result = await db_session.execute(select(PushSubscription))
        subs = list(result.scalars().all())
        assert len(subs) == 1
        assert subs[0].p256dh == "new-key"
        assert subs[0].auth == "new-auth"

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_from_db(self, client: AsyncClient, db_session: AsyncSession):
        """Unsubscribe via POST /api/push/unsubscribe, verify subscription removed."""
        await client.post(
            "/api/push/subscribe",
            json={
                "endpoint": "https://push.example.com/sub1",
                "keys": {"p256dh": "k", "auth": "a"},
            },
        )
        resp = await client.post(
            "/api/push/unsubscribe",
            json={"endpoint": "https://push.example.com/sub1"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "unsubscribed"}

        from sqlalchemy import select

        result = await db_session.execute(select(PushSubscription))
        subs = list(result.scalars().all())
        assert len(subs) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_is_idempotent(self, client: AsyncClient):
        """Unsubscribe with a non-existent endpoint returns 200 (idempotent)."""
        resp = await client.post(
            "/api/push/unsubscribe",
            json={"endpoint": "https://push.example.com/nonexistent"},
        )
        assert resp.status_code == 200


class TestSendEndpoint:
    @pytest.mark.asyncio
    async def test_send_with_no_subscriptions(self, client: AsyncClient):
        """POST /api/push/send with no subscriptions returns count 0."""
        resp = await client.post(
            "/api/push/send",
            json={"title": "Test", "body": "Hello"},
        )
        assert resp.status_code == 200
        assert resp.json()["delivered"] == 0

    @pytest.mark.asyncio
    async def test_send_calls_webpush(self, client: AsyncClient, db_session: AsyncSession):
        """POST /api/push/send sends to all stored subscriptions."""
        # Store a subscription first
        await client.post(
            "/api/push/subscribe",
            json={
                "endpoint": "https://push.example.com/sub1",
                "keys": {"p256dh": "k", "auth": "a"},
            },
        )

        with patch("codehive.api.routes.notifications.webpush") as mock_wp:
            resp = await client.post(
                "/api/push/send",
                json={"title": "Alert", "body": "Something happened", "url": "/sessions/1"},
            )
            assert resp.status_code == 200
            assert resp.json()["delivered"] == 1
            mock_wp.assert_called_once()
            call_kwargs = mock_wp.call_args
            assert call_kwargs.kwargs["subscription_info"]["endpoint"] == (
                "https://push.example.com/sub1"
            )
            data = json.loads(call_kwargs.kwargs["data"])
            assert data["title"] == "Alert"
            assert data["body"] == "Something happened"
            assert data["url"] == "/sessions/1"


# ---------------------------------------------------------------------------
# PushDispatcher tests
# ---------------------------------------------------------------------------


class TestPushDispatcher:
    @pytest.mark.asyncio
    async def test_approval_required_sends_push(self, session_factory):
        """Publish an approval.required event, verify webpush called."""
        settings = _make_settings()
        dispatcher = PushDispatcher(
            redis=AsyncMock(), session_factory=session_factory, settings=settings
        )

        # Insert a subscription
        async with session_factory() as db:
            sub = PushSubscription(endpoint="https://push.example.com/sub1", p256dh="k", auth="a")
            db.add(sub)
            await db.commit()

        msg = _make_pubsub_message(
            "approval.required",
            {"session_name": "deploy", "action_description": "drop table"},
        )

        with patch("codehive.core.notifications.webpush") as mock_wp:
            await dispatcher._handle_message(msg)
            mock_wp.assert_called_once()
            data = json.loads(mock_wp.call_args.kwargs["data"])
            assert data["title"] == "Approval Required"
            assert "deploy" in data["body"]
            assert data["event_type"] == "approval.required"

    @pytest.mark.asyncio
    async def test_session_completed_sends_to_all(self, session_factory):
        """Publish session.completed, verify sent to all subscriptions."""
        settings = _make_settings()
        dispatcher = PushDispatcher(
            redis=AsyncMock(), session_factory=session_factory, settings=settings
        )

        # Insert two subscriptions
        async with session_factory() as db:
            db.add(PushSubscription(endpoint="https://push.example.com/a", p256dh="k", auth="a"))
            db.add(PushSubscription(endpoint="https://push.example.com/b", p256dh="k", auth="a"))
            await db.commit()

        msg = _make_pubsub_message(
            "session.completed", {"session_name": "build", "summary": "All tests pass"}
        )

        with patch("codehive.core.notifications.webpush") as mock_wp:
            await dispatcher._handle_message(msg)
            assert mock_wp.call_count == 2

    @pytest.mark.asyncio
    async def test_stale_subscription_removed_on_410(self, session_factory):
        """Simulate a 410 Gone response, verify the stale subscription is deleted."""
        settings = _make_settings()
        dispatcher = PushDispatcher(
            redis=AsyncMock(), session_factory=session_factory, settings=settings
        )

        async with session_factory() as db:
            sub = PushSubscription(endpoint="https://push.example.com/stale", p256dh="k", auth="a")
            db.add(sub)
            await db.commit()

        msg = _make_pubsub_message("session.completed", {"session_name": "x", "summary": "y"})

        # Create a mock 410 response
        from pywebpush import WebPushException

        mock_response = MagicMock()
        mock_response.status_code = 410

        with patch(
            "codehive.core.notifications.webpush",
            side_effect=WebPushException("Gone", response=mock_response),
        ):
            await dispatcher._handle_message(msg)

        # Verify subscription was removed
        async with session_factory() as db:
            from sqlalchemy import select

            result = await db.execute(select(PushSubscription))
            subs = list(result.scalars().all())
            assert len(subs) == 0

    @pytest.mark.asyncio
    async def test_ignores_non_notification_events(self, session_factory):
        """Verify events outside the notification set do NOT trigger a push."""
        settings = _make_settings()
        dispatcher = PushDispatcher(
            redis=AsyncMock(), session_factory=session_factory, settings=settings
        )

        async with session_factory() as db:
            db.add(PushSubscription(endpoint="https://push.example.com/x", p256dh="k", auth="a"))
            await db.commit()

        msg = _make_pubsub_message("file.changed", {"path": "/src/main.py"})

        with patch("codehive.core.notifications.webpush") as mock_wp:
            await dispatcher._handle_message(msg)
            mock_wp.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_vapid_key(self, session_factory):
        """Dispatcher skips sending when VAPID private key is not set."""
        settings = _make_settings(vapid_private_key="")
        dispatcher = PushDispatcher(
            redis=AsyncMock(), session_factory=session_factory, settings=settings
        )

        async with session_factory() as db:
            db.add(PushSubscription(endpoint="https://push.example.com/x", p256dh="k", auth="a"))
            await db.commit()

        msg = _make_pubsub_message("session.completed", {"session_name": "x", "summary": "y"})

        with patch("codehive.core.notifications.webpush") as mock_wp:
            await dispatcher._handle_message(msg)
            mock_wp.assert_not_called()


class TestDispatcherLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_task(self, session_factory):
        settings = _make_settings()
        dispatcher = PushDispatcher(
            redis=AsyncMock(), session_factory=session_factory, settings=settings
        )

        async def _fake_listen() -> None:
            await asyncio.sleep(999)

        with patch.object(dispatcher, "_listen", side_effect=_fake_listen):
            await dispatcher.start()
            assert dispatcher._task is not None
            await dispatcher.stop()
            assert dispatcher._task is None

    @pytest.mark.asyncio
    async def test_redis_disconnect_logs_and_continues(self, session_factory):
        """Dispatcher logs error when Redis drops."""
        redis_mock = AsyncMock()
        pubsub_mock = AsyncMock()
        pubsub_mock.psubscribe = AsyncMock(side_effect=ConnectionError("Redis gone"))
        redis_mock.pubsub.return_value = pubsub_mock
        settings = _make_settings()
        dispatcher = PushDispatcher(
            redis=redis_mock, session_factory=session_factory, settings=settings
        )

        with patch("codehive.core.notifications.logger") as mock_logger:
            await dispatcher._listen()
            mock_logger.exception.assert_called_once()


# ---------------------------------------------------------------------------
# Payload builder tests
# ---------------------------------------------------------------------------


class TestBuildPayload:
    def test_approval_required_payload(self):
        payload = _build_payload(
            "approval.required",
            {"session_name": "deploy", "action_description": "drop db", "session_id": "s1"},
        )
        assert payload["title"] == "Approval Required"
        assert "deploy" in payload["body"]
        assert "drop db" in payload["body"]
        assert payload["url"] == "/sessions/s1"
        assert payload["event_type"] == "approval.required"

    def test_session_completed_payload(self):
        payload = _build_payload(
            "session.completed",
            {"session_name": "build", "summary": "All pass", "session_id": "s2"},
        )
        assert payload["title"] == "Session Completed"
        assert "build" in payload["body"]
        assert payload["url"] == "/sessions/s2"

    def test_session_failed_payload(self):
        payload = _build_payload(
            "session.failed",
            {"session_name": "ci", "error": "OOM", "session_id": "s3"},
        )
        assert payload["title"] == "Session Failed"
        assert "OOM" in payload["body"]

    def test_session_waiting_payload(self):
        payload = _build_payload(
            "session.waiting",
            {"session_name": "plan", "reason": "pending_question", "session_id": "s4"},
        )
        assert payload["title"] == "Session Waiting"
        assert "pending_question" in payload["body"]
