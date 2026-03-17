"""Tests for error tracking: ErrorTracker, ErrorRateMonitor, REST endpoints, Telegram formatter."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.clients.telegram.formatters import format_error_rate_spike_notification
from codehive.config import Settings
from codehive.core.error_tracking import ErrorRateMonitor, ErrorTracker, SYSTEM_SESSION_ID
from codehive.core.events import EventBus
from codehive.db.models import Base, Event, Project, Workspace
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
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
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


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
async def session_model(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="native",
        mode="execution",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def system_session(db_session: AsyncSession, project: Project) -> SessionModel:
    """Create a session with the SYSTEM_SESSION_ID for spike event publishing.

    Uses a hex string to avoid SQLite UUID round-trip issues.
    """
    sid = SYSTEM_SESSION_ID
    s = SessionModel(
        id=sid,
        project_id=project.id,
        name="system",
        engine="native",
        mode="execution",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


def _make_settings(**overrides) -> Settings:
    return Settings(
        error_window_minutes=overrides.get("error_window_minutes", 15),
        error_spike_threshold=overrides.get("error_spike_threshold", 3.0),
        error_spike_min_count=overrides.get("error_spike_min_count", 5),
        error_spike_cooldown_seconds=overrides.get("error_spike_cooldown_seconds", 300),
        error_monitor_interval_seconds=overrides.get("error_monitor_interval_seconds", 60),
    )


async def _insert_error(
    db: AsyncSession,
    session_id: uuid.UUID,
    event_type: str = "session.failed",
    data: dict | None = None,
    created_at: datetime | None = None,
) -> Event:
    ev = Event(
        session_id=session_id,
        type=event_type,
        data=data or {},
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ev


# ---------------------------------------------------------------------------
# Unit: ErrorTracker.get_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestErrorTrackerGetSummary:
    async def test_zero_errors(self, db_session, session_model):
        tracker = ErrorTracker(settings=_make_settings())
        summary = await tracker.get_summary(db_session)
        assert summary["total_errors"] == 0
        assert summary["window_errors"] == 0
        assert summary["errors_per_minute"] == 0.0
        assert summary["is_spike"] is False

    async def test_errors_in_window(self, db_session, session_model):
        now = datetime.now(timezone.utc)
        for i in range(3):
            await _insert_error(
                db_session,
                session_model.id,
                created_at=now - timedelta(minutes=i),
            )

        tracker = ErrorTracker(settings=_make_settings(error_window_minutes=15))
        summary = await tracker.get_summary(db_session)
        assert summary["window_errors"] == 3
        assert summary["errors_per_minute"] == round(3 / 15, 4)

    async def test_spike_detected(self, db_session, session_model):
        """Ratio exceeds threshold with enough errors -> is_spike=True."""
        now = datetime.now(timezone.utc)
        settings = _make_settings(
            error_window_minutes=15,
            error_spike_threshold=2.0,
            error_spike_min_count=3,
        )
        # Previous window: 2 errors
        for i in range(2):
            await _insert_error(
                db_session,
                session_model.id,
                created_at=now - timedelta(minutes=20 + i),
            )
        # Current window: 7 errors (ratio = 3.5 > 2.0)
        for i in range(7):
            await _insert_error(
                db_session,
                session_model.id,
                created_at=now - timedelta(minutes=i),
            )

        tracker = ErrorTracker(settings=settings)
        summary = await tracker.get_summary(db_session)
        assert summary["is_spike"] is True

    async def test_no_spike_below_threshold(self, db_session, session_model):
        """Ratio below threshold -> is_spike=False."""
        now = datetime.now(timezone.utc)
        settings = _make_settings(
            error_window_minutes=15,
            error_spike_threshold=3.0,
            error_spike_min_count=3,
        )
        # Previous window: 5 errors
        for i in range(5):
            await _insert_error(
                db_session,
                session_model.id,
                created_at=now - timedelta(minutes=20 + i),
            )
        # Current window: 6 errors (ratio = 1.2 < 3.0)
        for i in range(6):
            await _insert_error(
                db_session,
                session_model.id,
                created_at=now - timedelta(minutes=i),
            )

        tracker = ErrorTracker(settings=settings)
        summary = await tracker.get_summary(db_session)
        assert summary["is_spike"] is False

    async def test_no_spike_below_min_count(self, db_session, session_model):
        """High ratio but below min count -> is_spike=False."""
        now = datetime.now(timezone.utc)
        settings = _make_settings(
            error_window_minutes=15,
            error_spike_threshold=2.0,
            error_spike_min_count=10,
        )
        # Previous window: 1 error
        await _insert_error(
            db_session,
            session_model.id,
            created_at=now - timedelta(minutes=20),
        )
        # Current window: 3 errors (ratio = 3.0 > 2.0 but count < min_count=10)
        for i in range(3):
            await _insert_error(
                db_session,
                session_model.id,
                created_at=now - timedelta(minutes=i),
            )

        tracker = ErrorTracker(settings=settings)
        summary = await tracker.get_summary(db_session)
        assert summary["is_spike"] is False


# ---------------------------------------------------------------------------
# Unit: ErrorTracker.get_errors_by_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestErrorTrackerGetErrorsByType:
    async def test_grouped_by_type(self, db_session, session_model):
        now = datetime.now(timezone.utc)
        # 3 session.failed
        for _ in range(3):
            await _insert_error(db_session, session_model.id, "session.failed", created_at=now)
        # 2 tool.call.finished with error
        for _ in range(2):
            await _insert_error(
                db_session,
                session_model.id,
                "tool.call.finished",
                data={"error": "some error"},
                created_at=now,
            )

        tracker = ErrorTracker(settings=_make_settings())
        result = await tracker.get_errors_by_type(db_session)
        assert len(result) == 2
        assert result[0]["type"] == "session.failed"
        assert result[0]["count"] == 3
        assert result[1]["type"] == "tool.call.finished"
        assert result[1]["count"] == 2

    async def test_after_filter(self, db_session, session_model):
        now = datetime.now(timezone.utc)
        # Old error
        await _insert_error(db_session, session_model.id, created_at=now - timedelta(hours=2))
        # Recent error
        await _insert_error(db_session, session_model.id, created_at=now)

        tracker = ErrorTracker(settings=_make_settings())
        result = await tracker.get_errors_by_type(db_session, after=now - timedelta(hours=1))
        assert len(result) == 1
        assert result[0]["count"] == 1

    async def test_before_filter(self, db_session, session_model):
        now = datetime.now(timezone.utc)
        await _insert_error(db_session, session_model.id, created_at=now - timedelta(hours=2))
        await _insert_error(db_session, session_model.id, created_at=now)

        tracker = ErrorTracker(settings=_make_settings())
        result = await tracker.get_errors_by_type(db_session, before=now - timedelta(hours=1))
        assert len(result) == 1
        assert result[0]["count"] == 1

    async def test_after_and_before_filter(self, db_session, session_model):
        now = datetime.now(timezone.utc)
        await _insert_error(db_session, session_model.id, created_at=now - timedelta(hours=3))
        await _insert_error(db_session, session_model.id, created_at=now - timedelta(hours=1))
        await _insert_error(db_session, session_model.id, created_at=now)

        tracker = ErrorTracker(settings=_make_settings())
        result = await tracker.get_errors_by_type(
            db_session,
            after=now - timedelta(hours=2),
            before=now - timedelta(minutes=30),
        )
        assert len(result) == 1
        assert result[0]["count"] == 1

    async def test_limit(self, db_session, session_model):
        now = datetime.now(timezone.utc)
        for _ in range(3):
            await _insert_error(db_session, session_model.id, "session.failed", created_at=now)
        for _ in range(2):
            await _insert_error(
                db_session,
                session_model.id,
                "tool.call.finished",
                data={"error": "err"},
                created_at=now,
            )

        tracker = ErrorTracker(settings=_make_settings())
        result = await tracker.get_errors_by_type(db_session, limit=1)
        assert len(result) == 1
        assert result[0]["type"] == "session.failed"


# ---------------------------------------------------------------------------
# Unit: ErrorTracker.get_recent_errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestErrorTrackerGetRecentErrors:
    async def test_returns_most_recent_first(self, db_session, session_model):
        now = datetime.now(timezone.utc)
        for i in range(5):
            await _insert_error(
                db_session,
                session_model.id,
                created_at=now - timedelta(minutes=5 - i),
            )

        tracker = ErrorTracker(settings=_make_settings())
        result = await tracker.get_recent_errors(db_session, limit=3)
        assert len(result) == 3
        # Most recent first
        assert result[0].created_at >= result[1].created_at
        assert result[1].created_at >= result[2].created_at

    async def test_offset(self, db_session, session_model):
        now = datetime.now(timezone.utc)
        for i in range(5):
            await _insert_error(
                db_session,
                session_model.id,
                created_at=now - timedelta(minutes=i),
            )

        tracker = ErrorTracker(settings=_make_settings())
        result = await tracker.get_recent_errors(db_session, offset=2, limit=3)
        assert len(result) == 3

    async def test_event_type_filter(self, db_session, session_model):
        now = datetime.now(timezone.utc)
        await _insert_error(db_session, session_model.id, "session.failed", created_at=now)
        await _insert_error(
            db_session,
            session_model.id,
            "tool.call.finished",
            data={"error": "err"},
            created_at=now,
        )

        tracker = ErrorTracker(settings=_make_settings())
        result = await tracker.get_recent_errors(db_session, event_type="session.failed")
        assert len(result) == 1
        assert result[0].type == "session.failed"

    async def test_empty_returns_empty_list(self, db_session, session_model):
        tracker = ErrorTracker(settings=_make_settings())
        result = await tracker.get_recent_errors(db_session)
        assert result == []


# ---------------------------------------------------------------------------
# Unit: ErrorRateMonitor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestErrorRateMonitor:
    async def test_publishes_spike_event(
        self, db_session, session_model, system_session, session_factory
    ):
        """When spike conditions are met, an error.rate_spike event is published."""
        now = datetime.now(timezone.utc)
        settings = _make_settings(
            error_window_minutes=15,
            error_spike_threshold=2.0,
            error_spike_min_count=3,
            error_spike_cooldown_seconds=300,
        )
        # Previous window: 1 error
        await _insert_error(db_session, session_model.id, created_at=now - timedelta(minutes=20))
        # Current window: 5 errors
        for i in range(5):
            await _insert_error(db_session, session_model.id, created_at=now - timedelta(minutes=i))

        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(redis=mock_redis)

        monitor = ErrorRateMonitor(event_bus, session_factory, settings=settings)
        await monitor._check()

        # The event bus should have published an error.rate_spike event
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        channel = call_args[0][0]
        assert "events" in channel

    async def test_spike_event_includes_ratio(
        self, db_session, session_model, system_session, session_factory
    ):
        """The published spike event data must include spike_ratio and previous_window_errors."""
        import json

        now = datetime.now(timezone.utc)
        settings = _make_settings(
            error_window_minutes=15,
            error_spike_threshold=2.0,
            error_spike_min_count=3,
            error_spike_cooldown_seconds=300,
        )
        # Previous window: 2 errors
        for i in range(2):
            await _insert_error(
                db_session, session_model.id, created_at=now - timedelta(minutes=20 + i)
            )
        # Current window: 7 errors (ratio = 3.5)
        for i in range(7):
            await _insert_error(db_session, session_model.id, created_at=now - timedelta(minutes=i))

        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(redis=mock_redis)

        monitor = ErrorRateMonitor(event_bus, session_factory, settings=settings)
        await monitor._check()

        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        payload = json.loads(call_args[0][1])
        event_data = payload["data"]
        assert "spike_ratio" in event_data
        assert event_data["spike_ratio"] == 3.5
        assert "previous_window_errors" in event_data
        assert event_data["previous_window_errors"] == 2

    async def test_no_spike_below_min_count(
        self, db_session, session_model, system_session, session_factory
    ):
        """Below min_count, no spike event is published."""
        now = datetime.now(timezone.utc)
        settings = _make_settings(
            error_window_minutes=15,
            error_spike_threshold=2.0,
            error_spike_min_count=10,
        )
        # Current window: 3 errors (below min_count)
        for i in range(3):
            await _insert_error(db_session, session_model.id, created_at=now - timedelta(minutes=i))

        mock_redis = AsyncMock()
        event_bus = EventBus(redis=mock_redis)
        monitor = ErrorRateMonitor(event_bus, session_factory, settings=settings)
        await monitor._check()

        mock_redis.publish.assert_not_called()

    async def test_no_spike_below_threshold(
        self, db_session, session_model, system_session, session_factory
    ):
        """Ratio below threshold, no spike event is published."""
        now = datetime.now(timezone.utc)
        settings = _make_settings(
            error_window_minutes=15,
            error_spike_threshold=3.0,
            error_spike_min_count=3,
        )
        # Previous window: 5
        for i in range(5):
            await _insert_error(
                db_session, session_model.id, created_at=now - timedelta(minutes=20 + i)
            )
        # Current window: 6 (ratio=1.2 < 3.0)
        for i in range(6):
            await _insert_error(db_session, session_model.id, created_at=now - timedelta(minutes=i))

        mock_redis = AsyncMock()
        event_bus = EventBus(redis=mock_redis)
        monitor = ErrorRateMonitor(event_bus, session_factory, settings=settings)
        await monitor._check()

        mock_redis.publish.assert_not_called()

    async def test_cooldown_prevents_duplicate(
        self, db_session, session_model, system_session, session_factory
    ):
        """After a spike, cooldown prevents a second alert."""
        now = datetime.now(timezone.utc)
        settings = _make_settings(
            error_window_minutes=15,
            error_spike_threshold=2.0,
            error_spike_min_count=3,
            error_spike_cooldown_seconds=300,
        )
        # Previous window: 1 error
        await _insert_error(db_session, session_model.id, created_at=now - timedelta(minutes=20))
        # Current window: 5 errors
        for i in range(5):
            await _insert_error(db_session, session_model.id, created_at=now - timedelta(minutes=i))

        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(redis=mock_redis)

        monitor = ErrorRateMonitor(event_bus, session_factory, settings=settings)
        await monitor._check()
        assert mock_redis.publish.call_count == 1

        # Second check within cooldown should not publish again
        await monitor._check()
        assert mock_redis.publish.call_count == 1

    async def test_after_cooldown_can_fire_again(
        self, db_session, session_model, system_session, session_factory
    ):
        """After cooldown expires, a new spike can be published."""
        now = datetime.now(timezone.utc)
        settings = _make_settings(
            error_window_minutes=15,
            error_spike_threshold=2.0,
            error_spike_min_count=3,
            error_spike_cooldown_seconds=1,
        )
        # Previous window: 1 error
        await _insert_error(db_session, session_model.id, created_at=now - timedelta(minutes=20))
        # Current window: 5 errors
        for i in range(5):
            await _insert_error(db_session, session_model.id, created_at=now - timedelta(minutes=i))

        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(redis=mock_redis)

        monitor = ErrorRateMonitor(event_bus, session_factory, settings=settings)
        await monitor._check()
        assert mock_redis.publish.call_count == 1

        # Simulate cooldown expiry by resetting last_spike_time
        monitor._last_spike_time = 0.0

        await monitor._check()
        assert mock_redis.publish.call_count == 2


# ---------------------------------------------------------------------------
# Integration: REST endpoints
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/register",
            json={"email": "test@test.com", "username": "testuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


@pytest.mark.asyncio
class TestErrorTrackingEndpoints:
    async def test_summary_empty(self, client):
        resp = await client.get("/api/errors/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_errors"] == 0
        assert data["window_errors"] == 0
        assert data["errors_per_minute"] == 0.0
        assert data["is_spike"] is False
        assert "window_minutes" in data

    async def test_summary_with_errors(self, client, db_session, session_model):
        now = datetime.now(timezone.utc)
        for _ in range(3):
            await _insert_error(db_session, session_model.id, created_at=now)

        resp = await client.get("/api/errors/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_errors"] == 3
        assert data["window_errors"] == 3

    async def test_by_type_returns_list(self, client, db_session, session_model):
        now = datetime.now(timezone.utc)
        for _ in range(2):
            await _insert_error(db_session, session_model.id, "session.failed", created_at=now)

        resp = await client.get("/api/errors/by-type")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["type"] == "session.failed"
        assert data[0]["count"] == 2

    async def test_by_type_with_after(self, client, db_session, session_model):
        now = datetime.now(timezone.utc)
        await _insert_error(db_session, session_model.id, created_at=now - timedelta(hours=2))
        await _insert_error(db_session, session_model.id, created_at=now)

        after = (now - timedelta(hours=1)).isoformat()
        resp = await client.get("/api/errors/by-type", params={"after": after})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["count"] == 1

    async def test_recent_empty(self, client):
        resp = await client.get("/api/errors/recent")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_recent_returns_events(self, client, db_session, session_model):
        now = datetime.now(timezone.utc)
        for _ in range(3):
            await _insert_error(db_session, session_model.id, created_at=now)

        resp = await client.get("/api/errors/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        for item in data:
            assert "id" in item
            assert "session_id" in item
            assert "type" in item
            assert "data" in item
            assert "created_at" in item

    async def test_recent_event_type_filter(self, client, db_session, session_model):
        now = datetime.now(timezone.utc)
        await _insert_error(db_session, session_model.id, "session.failed", created_at=now)
        await _insert_error(
            db_session,
            session_model.id,
            "tool.call.finished",
            data={"error": "err"},
            created_at=now,
        )

        resp = await client.get("/api/errors/recent?event_type=session.failed")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["type"] == "session.failed"

    async def test_recent_pagination(self, client, db_session, session_model):
        now = datetime.now(timezone.utc)
        for i in range(5):
            await _insert_error(
                db_session,
                session_model.id,
                created_at=now - timedelta(minutes=i),
            )

        resp = await client.get("/api/errors/recent?limit=2&offset=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2


# ---------------------------------------------------------------------------
# Integration: Telegram notification formatter
# ---------------------------------------------------------------------------


class TestTelegramErrorFormatter:
    def test_format_error_rate_spike(self):
        data = {
            "window_errors": 15,
            "window_minutes": 10,
            "errors_per_minute": 1.5,
            "spike_ratio": 3.5,
        }
        text = format_error_rate_spike_notification(data)
        assert "15" in text
        assert "10" in text
        assert "1.50" in text
        assert "spike" in text.lower()
        assert "3.5x normal" in text

    def test_format_error_rate_spike_without_ratio(self):
        data = {
            "window_errors": 15,
            "window_minutes": 10,
            "errors_per_minute": 1.5,
        }
        text = format_error_rate_spike_notification(data)
        assert "15" in text
        assert "ratio" not in text.lower()


# ---------------------------------------------------------------------------
# Unit: Settings fields exist
# ---------------------------------------------------------------------------


class TestSettingsErrorTracking:
    def test_error_tracking_settings_defaults(self):
        settings = Settings()
        assert settings.error_window_minutes == 15
        assert settings.error_spike_threshold == 3.0
        assert settings.error_spike_min_count == 5
        assert settings.error_spike_cooldown_seconds == 300
        assert settings.error_monitor_interval_seconds == 60
