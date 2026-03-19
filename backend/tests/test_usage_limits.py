"""Tests for issue #122: Plan usage limits and per-model breakdown.

Covers ClaudeCodeParser rate_limit_event handling, model usage extraction,
DB storage, and API endpoint.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.db.models import (
    Base,
    ModelUsageSnapshot,
    Project,
    RateLimitSnapshot,
)
from codehive.db.models import Session as SessionModel
from codehive.engine.claude_code_parser import ClaudeCodeParser

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
        name="limits-test-project",
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
        name="limits-test-session",
        engine="claude_code",
        mode="execution",
        status="idle",
        config={},
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
                "email": "test@limits.com",
                "username": "limitsuser",
                "password": "testpass",
            },
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit tests: ClaudeCodeParser rate_limit_event handling
# ---------------------------------------------------------------------------


class TestParserRateLimitEvent:
    def setup_method(self):
        self.parser = ClaudeCodeParser()
        self.sid = uuid.uuid4()

    def test_parse_rate_limit_event(self):
        line = json.dumps(
            {
                "type": "rate_limit_event",
                "rate_limit_info": {
                    "status": "allowed_warning",
                    "resetsAt": 1773997200,
                    "rateLimitType": "seven_day",
                    "utilization": 0.92,
                    "isUsingOverage": False,
                    "surpassedThreshold": 0.75,
                },
            }
        )
        events = self.parser.parse_line(line, self.sid)
        assert len(events) == 1
        ev = events[0]
        assert ev["type"] == "rate_limit.updated"
        assert ev["rate_limit_type"] == "seven_day"
        assert ev["utilization"] == 0.92
        assert ev["resets_at"] == 1773997200
        assert ev["is_using_overage"] is False
        assert ev["surpassed_threshold"] == 0.75

    def test_parse_rate_limit_event_utilization_float(self):
        line = json.dumps(
            {
                "type": "rate_limit_event",
                "rate_limit_info": {
                    "rateLimitType": "seven_day",
                    "utilization": 0.5,
                    "resetsAt": 1773997200,
                    "isUsingOverage": False,
                },
            }
        )
        events = self.parser.parse_line(line, self.sid)
        assert len(events) == 1
        assert isinstance(events[0]["utilization"], float)
        assert events[0]["utilization"] == 0.5

    def test_parse_rate_limit_event_with_overage(self):
        line = json.dumps(
            {
                "type": "rate_limit_event",
                "rate_limit_info": {
                    "rateLimitType": "seven_day",
                    "utilization": 0.99,
                    "resetsAt": 1773997200,
                    "isUsingOverage": True,
                    "surpassedThreshold": 0.95,
                },
            }
        )
        events = self.parser.parse_line(line, self.sid)
        assert len(events) == 1
        assert events[0]["is_using_overage"] is True

    def test_parse_rate_limit_event_missing_info(self):
        line = json.dumps({"type": "rate_limit_event", "rate_limit_info": {}})
        events = self.parser.parse_line(line, self.sid)
        assert len(events) == 0

    def test_parse_rate_limit_event_no_info_key(self):
        line = json.dumps({"type": "rate_limit_event"})
        events = self.parser.parse_line(line, self.sid)
        assert len(events) == 0


# ---------------------------------------------------------------------------
# Unit tests: ClaudeCodeParser result modelUsage handling
# ---------------------------------------------------------------------------


class TestParserModelUsage:
    def setup_method(self):
        self.parser = ClaudeCodeParser()
        self.sid = uuid.uuid4()

    def test_parse_result_with_model_usage(self):
        line = json.dumps(
            {
                "type": "result",
                "content": [{"type": "text", "text": "Done."}],
                "modelUsage": {
                    "claude-opus-4-20250514": {
                        "inputTokens": 5000,
                        "outputTokens": 1200,
                        "cacheReadInputTokens": 3000,
                        "cacheCreationInputTokens": 500,
                        "costUSD": 0.07,
                        "contextWindow": 200000,
                        "maxOutputTokens": 16000,
                    }
                },
                "total_cost_usd": 0.07,
            }
        )
        events = self.parser.parse_line(line, self.sid)
        # Should produce message.created + usage.model_breakdown
        assert len(events) == 2
        msg_ev = events[0]
        assert msg_ev["type"] == "message.created"

        usage_ev = events[1]
        assert usage_ev["type"] == "usage.model_breakdown"
        assert usage_ev["total_cost_usd"] == 0.07
        assert len(usage_ev["models"]) == 1

        model = usage_ev["models"][0]
        assert model["model"] == "claude-opus-4-20250514"
        assert model["input_tokens"] == 5000
        assert model["output_tokens"] == 1200
        assert model["cache_read_tokens"] == 3000
        assert model["cache_creation_tokens"] == 500
        assert model["cost_usd"] == 0.07
        assert model["context_window"] == 200000

    def test_parse_result_without_model_usage(self):
        line = json.dumps(
            {
                "type": "result",
                "content": [{"type": "text", "text": "Done."}],
            }
        )
        events = self.parser.parse_line(line, self.sid)
        # Only message.created, no usage.model_breakdown
        assert len(events) == 1
        assert events[0]["type"] == "message.created"

    def test_parse_result_empty_model_usage(self):
        line = json.dumps(
            {
                "type": "result",
                "content": [{"type": "text", "text": "Done."}],
                "modelUsage": {},
            }
        )
        events = self.parser.parse_line(line, self.sid)
        assert len(events) == 1
        assert events[0]["type"] == "message.created"

    def test_parse_result_multiple_models(self):
        line = json.dumps(
            {
                "type": "result",
                "content": [{"type": "text", "text": "Done."}],
                "modelUsage": {
                    "claude-opus-4-20250514": {
                        "inputTokens": 5000,
                        "outputTokens": 1200,
                        "costUSD": 0.10,
                    },
                    "claude-sonnet-4-20250514": {
                        "inputTokens": 2000,
                        "outputTokens": 800,
                        "costUSD": 0.02,
                    },
                },
                "total_cost_usd": 0.12,
            }
        )
        events = self.parser.parse_line(line, self.sid)
        assert len(events) == 2
        usage_ev = events[1]
        assert usage_ev["type"] == "usage.model_breakdown"
        assert len(usage_ev["models"]) == 2


# ---------------------------------------------------------------------------
# Unit tests: Rate limit storage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRateLimitStorage:
    async def test_store_and_retrieve(self, db_session: AsyncSession, session_model: SessionModel):
        snap = RateLimitSnapshot(
            session_id=session_model.id,
            rate_limit_type="seven_day",
            utilization=0.92,
            resets_at=1773997200,
            is_using_overage=False,
            surpassed_threshold=0.75,
        )
        db_session.add(snap)
        await db_session.commit()
        await db_session.refresh(snap)

        assert snap.id is not None
        assert snap.rate_limit_type == "seven_day"
        assert snap.utilization == 0.92
        assert snap.resets_at == 1773997200
        assert snap.is_using_overage is False
        assert snap.surpassed_threshold == 0.75

    async def test_store_two_types(self, db_session: AsyncSession, session_model: SessionModel):
        from sqlalchemy import select

        for rlt in ("seven_day", "hourly"):
            snap = RateLimitSnapshot(
                session_id=session_model.id,
                rate_limit_type=rlt,
                utilization=0.5,
                resets_at=1773997200,
            )
            db_session.add(snap)
        await db_session.commit()

        result = await db_session.execute(select(RateLimitSnapshot))
        rows = result.scalars().all()
        types = {r.rate_limit_type for r in rows}
        assert types == {"seven_day", "hourly"}

    async def test_store_model_usage(self, db_session: AsyncSession, session_model: SessionModel):
        from sqlalchemy import select

        snap = ModelUsageSnapshot(
            session_id=session_model.id,
            model="claude-opus-4-20250514",
            input_tokens=5000,
            output_tokens=1200,
            cache_read_tokens=3000,
            cache_creation_tokens=500,
            cost_usd=0.07,
            context_window=200000,
        )
        db_session.add(snap)
        await db_session.commit()
        await db_session.refresh(snap)

        result = await db_session.execute(select(ModelUsageSnapshot))
        rows = result.scalars().all()
        assert len(rows) == 1
        m = rows[0]
        assert m.model == "claude-opus-4-20250514"
        assert m.input_tokens == 5000
        assert m.output_tokens == 1200
        assert m.cache_read_tokens == 3000
        assert m.cache_creation_tokens == 500
        assert m.cost_usd == 0.07
        assert m.context_window == 200000


# ---------------------------------------------------------------------------
# Integration tests: API endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUsageLimitsAPI:
    async def test_get_limits_empty(self, client: AsyncClient):
        resp = await client.get("/api/usage/limits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_limits"] == []
        assert data["model_usage"] == []

    async def test_get_limits_with_data(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        snap = RateLimitSnapshot(
            session_id=session_model.id,
            rate_limit_type="seven_day",
            utilization=0.85,
            resets_at=1773997200,
            is_using_overage=False,
            surpassed_threshold=0.75,
        )
        db_session.add(snap)

        mu = ModelUsageSnapshot(
            session_id=session_model.id,
            model="claude-opus-4-20250514",
            input_tokens=5000,
            output_tokens=1200,
            cache_read_tokens=3000,
            cache_creation_tokens=500,
            cost_usd=0.07,
            context_window=200000,
        )
        db_session.add(mu)
        await db_session.commit()

        resp = await client.get("/api/usage/limits")
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["rate_limits"]) == 1
        rl = data["rate_limits"][0]
        assert rl["rate_limit_type"] == "seven_day"
        assert rl["utilization"] == 0.85
        assert rl["resets_at"] == 1773997200
        assert rl["is_using_overage"] is False

        assert len(data["model_usage"]) == 1
        mu_data = data["model_usage"][0]
        assert mu_data["model"] == "claude-opus-4-20250514"
        assert mu_data["input_tokens"] == 5000
        assert mu_data["cost_usd"] == 0.07

    async def test_get_limits_returns_latest_per_type(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        from datetime import timedelta

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Older snapshot
        old = RateLimitSnapshot(
            session_id=session_model.id,
            rate_limit_type="seven_day",
            utilization=0.50,
            resets_at=1773990000,
            captured_at=now - timedelta(hours=2),
        )
        db_session.add(old)

        # Newer snapshot
        new = RateLimitSnapshot(
            session_id=session_model.id,
            rate_limit_type="seven_day",
            utilization=0.92,
            resets_at=1773997200,
            captured_at=now,
        )
        db_session.add(new)
        await db_session.commit()

        resp = await client.get("/api/usage/limits")
        data = resp.json()
        assert len(data["rate_limits"]) == 1
        assert data["rate_limits"][0]["utilization"] == 0.92
