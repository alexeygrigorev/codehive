"""Tests for issue #128: persist_usage_event helper and consumer wiring.

Covers the shared helper function that persists RateLimitSnapshot and
ModelUsageSnapshot rows from engine events, plus integration tests verifying
the helper is wired into the message consumers.
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.usage import persist_usage_event
from codehive.db.models import (
    Base,
    ModelUsageSnapshot,
    Project,
    RateLimitSnapshot,
)
from codehive.db.models import Session as SessionModel

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
async def project(db_session: AsyncSession) -> Project:
    proj = Project(
        name="persist-test-project",
        knowledge={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest_asyncio.fixture
async def session_model(db_session: AsyncSession, project: Project) -> SessionModel:
    sess = SessionModel(
        project_id=project.id,
        name="persist-test-session",
        engine="claude_code",
        mode="execution",
        status="idle",
        config={"project_root": "/tmp"},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(sess)
    await db_session.commit()
    await db_session.refresh(sess)
    return sess


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
            json={
                "email": "test@persist128.com",
                "username": "persistuser128",
                "password": "testpass",
            },
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit tests: persist_usage_event helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPersistUsageEventHelper:
    async def test_rate_limit_event_creates_snapshot(
        self, db_session: AsyncSession, session_model: SessionModel
    ):
        event_dict = {
            "type": "rate_limit.updated",
            "session_id": str(session_model.id),
            "rate_limit_type": "seven_day",
            "utilization": 0.85,
            "resets_at": 1773997200,
            "is_using_overage": False,
            "surpassed_threshold": 0.75,
        }
        await persist_usage_event(db_session, session_model.id, event_dict)
        await db_session.commit()

        result = await db_session.execute(select(RateLimitSnapshot))
        rows = result.scalars().all()
        assert len(rows) == 1
        snap = rows[0]
        assert snap.session_id == session_model.id
        assert snap.rate_limit_type == "seven_day"
        assert snap.utilization == 0.85
        assert snap.resets_at == 1773997200
        assert snap.is_using_overage is False
        assert snap.surpassed_threshold == 0.75

    async def test_model_breakdown_creates_snapshots(
        self, db_session: AsyncSession, session_model: SessionModel
    ):
        event_dict = {
            "type": "usage.model_breakdown",
            "session_id": str(session_model.id),
            "models": [
                {
                    "model": "claude-opus-4-20250514",
                    "input_tokens": 5000,
                    "output_tokens": 1200,
                    "cache_read_tokens": 3000,
                    "cache_creation_tokens": 500,
                    "cost_usd": 0.07,
                    "context_window": 200000,
                },
                {
                    "model": "claude-sonnet-4-20250514",
                    "input_tokens": 2000,
                    "output_tokens": 800,
                    "cache_read_tokens": 1000,
                    "cache_creation_tokens": 200,
                    "cost_usd": 0.02,
                    "context_window": 200000,
                },
            ],
            "total_cost_usd": 0.09,
        }
        await persist_usage_event(db_session, session_model.id, event_dict)
        await db_session.commit()

        result = await db_session.execute(select(ModelUsageSnapshot))
        rows = result.scalars().all()
        assert len(rows) == 2

        by_model = {r.model: r for r in rows}
        opus = by_model["claude-opus-4-20250514"]
        assert opus.input_tokens == 5000
        assert opus.output_tokens == 1200
        assert opus.cache_read_tokens == 3000
        assert opus.cache_creation_tokens == 500
        assert opus.cost_usd == 0.07
        assert opus.context_window == 200000

        sonnet = by_model["claude-sonnet-4-20250514"]
        assert sonnet.input_tokens == 2000
        assert sonnet.output_tokens == 800

    async def test_unrelated_event_no_rows(
        self, db_session: AsyncSession, session_model: SessionModel
    ):
        event_dict = {
            "type": "message.created",
            "role": "assistant",
            "content": "Hello",
            "session_id": str(session_model.id),
        }
        await persist_usage_event(db_session, session_model.id, event_dict)
        await db_session.commit()

        rl_result = await db_session.execute(select(RateLimitSnapshot))
        assert len(rl_result.scalars().all()) == 0

        mu_result = await db_session.execute(select(ModelUsageSnapshot))
        assert len(mu_result.scalars().all()) == 0

    async def test_rate_limit_event_with_none_session_id(self, db_session: AsyncSession):
        event_dict = {
            "type": "rate_limit.updated",
            "session_id": None,
            "rate_limit_type": "hourly",
            "utilization": 0.50,
            "resets_at": 1773990000,
            "is_using_overage": False,
        }
        await persist_usage_event(db_session, None, event_dict)
        await db_session.commit()

        result = await db_session.execute(select(RateLimitSnapshot))
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].session_id is None
        assert rows[0].rate_limit_type == "hourly"
        assert rows[0].utilization == 0.50

    async def test_model_breakdown_empty_models_list(
        self, db_session: AsyncSession, session_model: SessionModel
    ):
        event_dict = {
            "type": "usage.model_breakdown",
            "session_id": str(session_model.id),
            "models": [],
        }
        await persist_usage_event(db_session, session_model.id, event_dict)
        await db_session.commit()

        result = await db_session.execute(select(ModelUsageSnapshot))
        assert len(result.scalars().all()) == 0


# ---------------------------------------------------------------------------
# Integration tests: API endpoint round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPersistUsageEventIntegration:
    async def test_send_message_persists_rate_limit(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """Mock engine yields rate_limit.updated; verify GET /api/usage/limits returns it."""
        from unittest.mock import AsyncMock, patch

        async def _fake_send_message(*args, **kwargs):
            yield {
                "type": "rate_limit.updated",
                "session_id": str(session_model.id),
                "rate_limit_type": "seven_day",
                "utilization": 0.88,
                "resets_at": 1773997200,
                "is_using_overage": False,
                "surpassed_threshold": 0.80,
            }
            yield {
                "type": "message.created",
                "role": "assistant",
                "content": "Hello",
                "session_id": str(session_model.id),
            }

        mock_engine = AsyncMock()
        mock_engine.send_message = _fake_send_message
        mock_engine.create_session = AsyncMock()

        with patch(
            "codehive.api.routes.sessions._build_engine",
            return_value=mock_engine,
        ):
            resp = await client.post(
                f"/api/sessions/{session_model.id}/messages",
                json={"content": "hi"},
            )
            assert resp.status_code == 200

        # Now verify the data is in the DB via the API
        resp = await client.get("/api/usage/limits")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rate_limits"]) == 1
        rl = data["rate_limits"][0]
        assert rl["rate_limit_type"] == "seven_day"
        assert rl["utilization"] == 0.88
        assert rl["resets_at"] == 1773997200

    async def test_send_message_persists_model_usage(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """Mock engine yields usage.model_breakdown; verify GET /api/usage/limits returns it."""
        from unittest.mock import AsyncMock, patch

        async def _fake_send_message(*args, **kwargs):
            yield {
                "type": "message.created",
                "role": "assistant",
                "content": "Done.",
                "session_id": str(session_model.id),
            }
            yield {
                "type": "usage.model_breakdown",
                "session_id": str(session_model.id),
                "models": [
                    {
                        "model": "claude-opus-4-20250514",
                        "input_tokens": 5000,
                        "output_tokens": 1200,
                        "cache_read_tokens": 3000,
                        "cache_creation_tokens": 500,
                        "cost_usd": 0.07,
                        "context_window": 200000,
                    }
                ],
                "total_cost_usd": 0.07,
            }

        mock_engine = AsyncMock()
        mock_engine.send_message = _fake_send_message
        mock_engine.create_session = AsyncMock()

        with patch(
            "codehive.api.routes.sessions._build_engine",
            return_value=mock_engine,
        ):
            resp = await client.post(
                f"/api/sessions/{session_model.id}/messages",
                json={"content": "hi"},
            )
            assert resp.status_code == 200

        resp = await client.get("/api/usage/limits")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["model_usage"]) == 1
        mu = data["model_usage"][0]
        assert mu["model"] == "claude-opus-4-20250514"
        assert mu["input_tokens"] == 5000
        assert mu["output_tokens"] == 1200
        assert mu["cost_usd"] == 0.07

    async def test_get_limits_empty_when_no_events(
        self,
        client: AsyncClient,
    ):
        """Verify the limits endpoint still works with no data."""
        resp = await client.get("/api/usage/limits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_limits"] == []
        assert data["model_usage"] == []
