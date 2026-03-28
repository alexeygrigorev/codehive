"""Tests for EngineThrottleTracker and orchestrator throttle integration."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.engine_throttle import EngineThrottleTracker
from codehive.core.orchestrator_service import (
    OrchestratorService,
    clear_registry,
    get_orchestrator,
)
from codehive.db.models import Base, Project
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
async def db_session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(db_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with db_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def project(db_session: AsyncSession) -> Project:
    proj = Project(
        name="throttle-test-project",
        knowledge={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest_asyncio.fixture
async def orch_session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name=f"orchestrator-{project.id}",
        engine="claude_code",
        mode="orchestrator",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture(autouse=True)
async def cleanup_registry():
    clear_registry()
    yield
    clear_registry()


# ---------------------------------------------------------------------------
# Unit: EngineThrottleTracker
# ---------------------------------------------------------------------------


class TestEngineThrottleTracker:
    def test_mark_throttled_future_makes_unavailable(self):
        tracker = EngineThrottleTracker()
        future = int(time.time()) + 300  # 5 minutes from now
        tracker.mark_throttled("claude_code", future)
        assert tracker.is_available("claude_code") is False

    def test_mark_throttled_past_is_available(self):
        tracker = EngineThrottleTracker()
        past = int(time.time()) - 60  # 1 minute ago
        tracker.mark_throttled("claude_code", past)
        assert tracker.is_available("claude_code") is True

    def test_unknown_engine_is_available(self):
        tracker = EngineThrottleTracker()
        assert tracker.is_available("some_engine") is True

    def test_get_available_skips_throttled(self):
        tracker = EngineThrottleTracker()
        future = int(time.time()) + 300
        tracker.mark_throttled("claude_code", future)
        result = tracker.get_available(["claude_code", "codex_cli"])
        assert result == "codex_cli"

    def test_get_available_returns_none_when_all_throttled(self):
        tracker = EngineThrottleTracker()
        future = int(time.time()) + 300
        tracker.mark_throttled("claude_code", future)
        tracker.mark_throttled("codex_cli", future)
        result = tracker.get_available(["claude_code", "codex_cli"])
        assert result is None

    def test_get_available_returns_first_when_none_throttled(self):
        tracker = EngineThrottleTracker()
        result = tracker.get_available(["claude_code", "codex_cli"])
        assert result == "claude_code"

    def test_throttle_expires_automatically(self):
        """Throttle with very short TTL expires after brief sleep."""
        tracker = EngineThrottleTracker()
        # Set resets_at to ~0.1 seconds from now
        near_future = time.time() + 0.1
        tracker.mark_throttled("claude_code", int(near_future) + 1)
        # Should be throttled now
        assert tracker.is_available("claude_code") is False
        # Override with a past timestamp to simulate expiry
        past = int(time.time()) - 1
        tracker.mark_throttled("claude_code", past)
        assert tracker.is_available("claude_code") is True

    def test_get_status_shows_throttled_engine(self):
        tracker = EngineThrottleTracker()
        future = int(time.time()) + 300
        tracker.mark_throttled("claude_code", future)
        status = tracker.get_status()
        assert "claude_code" in status
        assert status["claude_code"]["available"] is False
        assert status["claude_code"]["throttled_until"] is not None
        assert "throttled" in status["claude_code"]["reason"]

    def test_get_status_shows_expired_engine(self):
        tracker = EngineThrottleTracker()
        past = int(time.time()) - 60
        tracker.mark_throttled("claude_code", past)
        status = tracker.get_status()
        assert "claude_code" in status
        assert status["claude_code"]["available"] is True
        assert status["claude_code"]["throttled_until"] is None


# ---------------------------------------------------------------------------
# Unit: _resolve_sub_agent_engine with throttle awareness
# ---------------------------------------------------------------------------


class TestResolveSubAgentEngineThrottled:
    def test_no_throttled_returns_first(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"sub_agent_engines": ["claude_code", "codex_cli"]},
        )
        assert service._resolve_sub_agent_engine() == "claude_code"

    def test_first_throttled_returns_second(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"sub_agent_engines": ["claude_code", "codex_cli"]},
        )
        future = int(time.time()) + 300
        service._throttle_tracker.mark_throttled("claude_code", future)
        assert service._resolve_sub_agent_engine() == "codex_cli"

    def test_all_throttled_returns_first_fallback(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"sub_agent_engines": ["claude_code", "codex_cli"]},
        )
        future = int(time.time()) + 300
        service._throttle_tracker.mark_throttled("claude_code", future)
        service._throttle_tracker.mark_throttled("codex_cli", future)
        # Sync method falls back to first engine
        assert service._resolve_sub_agent_engine() == "claude_code"


# ---------------------------------------------------------------------------
# Unit: _resolve_sub_agent_engine_with_retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestResolveWithRetry:
    async def test_retry_returns_available_engine(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"sub_agent_engines": ["claude_code", "codex_cli"]},
        )
        result = await service._resolve_sub_agent_engine_with_retry()
        assert result == "claude_code"

    async def test_retry_skips_throttled(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"sub_agent_engines": ["claude_code", "codex_cli"]},
        )
        future = int(time.time()) + 300
        service._throttle_tracker.mark_throttled("claude_code", future)
        result = await service._resolve_sub_agent_engine_with_retry()
        assert result == "codex_cli"

    async def test_retry_raises_when_all_throttled(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"sub_agent_engines": ["claude_code", "codex_cli"]},
        )
        future = int(time.time()) + 600
        service._throttle_tracker.mark_throttled("claude_code", future)
        service._throttle_tracker.mark_throttled("codex_cli", future)
        with pytest.raises(RuntimeError, match="All engines throttled"):
            await service._resolve_sub_agent_engine_with_retry()


# ---------------------------------------------------------------------------
# Unit: handle_rate_limit_event
# ---------------------------------------------------------------------------


class TestHandleRateLimitEvent:
    def test_high_utilization_throttles_engine(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"sub_agent_engines": ["claude_code", "codex_cli"]},
        )
        future = int(time.time()) + 300
        service.handle_rate_limit_event(
            "claude_code",
            {"utilization": 0.95, "resets_at": future},
        )
        assert service._throttle_tracker.is_available("claude_code") is False

    def test_low_utilization_does_not_throttle(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"sub_agent_engines": ["claude_code", "codex_cli"]},
        )
        future = int(time.time()) + 300
        service.handle_rate_limit_event(
            "claude_code",
            {"utilization": 0.50, "resets_at": future},
        )
        assert service._throttle_tracker.is_available("claude_code") is True

    def test_custom_threshold(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={
                "sub_agent_engines": ["claude_code"],
                "throttle_utilization_threshold": 0.90,
            },
        )
        future = int(time.time()) + 300
        # 0.85 is below 0.90 threshold -- should NOT throttle
        service.handle_rate_limit_event(
            "claude_code",
            {"utilization": 0.85, "resets_at": future},
        )
        assert service._throttle_tracker.is_available("claude_code") is True

        # 0.95 is above 0.90 threshold -- should throttle
        service.handle_rate_limit_event(
            "claude_code",
            {"utilization": 0.95, "resets_at": future},
        )
        assert service._throttle_tracker.is_available("claude_code") is False

    def test_zero_resets_at_does_not_throttle(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
        )
        service.handle_rate_limit_event(
            "claude_code",
            {"utilization": 0.95, "resets_at": 0},
        )
        assert service._throttle_tracker.is_available("claude_code") is True


# ---------------------------------------------------------------------------
# Unit: get_status includes engine_status
# ---------------------------------------------------------------------------


class TestGetStatusEngineStatus:
    def test_get_status_includes_engine_status(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"sub_agent_engines": ["claude_code", "codex_cli"]},
        )
        status = service.get_status()
        assert "engine_status" in status
        assert "claude_code" in status["engine_status"]
        assert "codex_cli" in status["engine_status"]
        assert status["engine_status"]["claude_code"]["available"] is True
        assert status["engine_status"]["codex_cli"]["available"] is True

    def test_get_status_shows_throttled_engine(self):
        service = OrchestratorService(
            db_session_factory=AsyncMock(),
            project_id=uuid.uuid4(),
            config={"sub_agent_engines": ["claude_code", "codex_cli"]},
        )
        future = int(time.time()) + 300
        service._throttle_tracker.mark_throttled("claude_code", future)
        status = service.get_status()
        assert status["engine_status"]["claude_code"]["available"] is False
        assert status["engine_status"]["claude_code"]["throttled_until"] is not None
        assert status["engine_status"]["codex_cli"]["available"] is True


# ---------------------------------------------------------------------------
# Integration: API endpoint returns engine_status
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
            json={"email": "throttle@test.com", "username": "throttleuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


@pytest.mark.asyncio
class TestAPIEngineStatus:
    async def test_status_endpoint_includes_engine_status(
        self,
        client: AsyncClient,
        project: Project,
    ):
        # Start orchestrator
        resp = await client.post(
            "/api/orchestrator/start",
            json={"project_id": str(project.id)},
        )
        assert resp.status_code == 200

        # Get status
        resp = await client.get(
            "/api/orchestrator/status",
            params={"project_id": str(project.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "engine_status" in data
        # Default engine is claude_code
        assert "claude_code" in data["engine_status"]
        assert data["engine_status"]["claude_code"]["available"] is True

        # Clean up
        svc = get_orchestrator(project.id)
        if svc:
            await svc.stop()

    async def test_status_endpoint_shows_throttled(
        self,
        client: AsyncClient,
        project: Project,
    ):
        # Start orchestrator with two engines
        resp = await client.post(
            "/api/orchestrator/start",
            json={
                "project_id": str(project.id),
                "config": {"sub_agent_engines": ["claude_code", "codex_cli"]},
            },
        )
        assert resp.status_code == 200

        # Throttle one engine via the service directly
        svc = get_orchestrator(project.id)
        assert svc is not None
        future = int(time.time()) + 300
        svc.handle_rate_limit_event(
            "claude_code",
            {"utilization": 0.95, "resets_at": future},
        )

        # Get status
        resp = await client.get(
            "/api/orchestrator/status",
            params={"project_id": str(project.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["engine_status"]["claude_code"]["available"] is False
        assert data["engine_status"]["codex_cli"]["available"] is True

        await svc.stop()

    async def test_status_stopped_has_no_engine_status(
        self,
        client: AsyncClient,
        project: Project,
    ):
        """When no orchestrator is running, engine_status is None."""
        resp = await client.get(
            "/api/orchestrator/status",
            params={"project_id": str(project.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["engine_status"] is None
