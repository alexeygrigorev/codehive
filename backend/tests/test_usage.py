"""Tests for usage tracking: model, API endpoints, and cost estimation."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.usage import (
    MODEL_CONTEXT_WINDOWS,
    estimate_cost,
    get_context_usage,
    get_context_window,
)
from codehive.db.models import Base, Project, UsageRecord
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
        name="usage-test-project",
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
        name="usage-test-session",
        engine="native",
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
async def usage_records(db_session: AsyncSession, session_model: SessionModel) -> list[UsageRecord]:
    records = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i in range(3):
        rec = UsageRecord(
            session_id=session_model.id,
            model="claude-sonnet-4-20250514",
            input_tokens=1000 * (i + 1),
            output_tokens=500 * (i + 1),
            created_at=now - timedelta(days=i),
        )
        db_session.add(rec)
        records.append(rec)
    await db_session.commit()
    for rec in records:
        await db_session.refresh(rec)
    return records


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register a test user
        resp = await ac.post(
            "/api/auth/register",
            json={
                "email": "test@usage.com",
                "username": "usageuser",
                "password": "testpass",
            },
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit tests: Cost estimation
# ---------------------------------------------------------------------------


class TestCostEstimation:
    def test_known_model_sonnet(self):
        cost = estimate_cost("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
        # $3/MTok input + $15/MTok output = $18
        assert cost == 18.0

    def test_known_model_opus(self):
        cost = estimate_cost("claude-opus-4-20250514", 1_000_000, 1_000_000)
        # $15/MTok input + $75/MTok output = $90
        assert cost == 90.0

    def test_small_token_count(self):
        cost = estimate_cost("claude-sonnet-4-20250514", 1000, 500)
        # (1000 * 3 + 500 * 15) / 1_000_000 = (3000 + 7500) / 1_000_000 = 0.0105
        assert cost == 0.0105

    def test_zero_tokens(self):
        cost = estimate_cost("claude-sonnet-4-20250514", 0, 0)
        assert cost == 0.0

    def test_unknown_model_uses_fallback(self):
        cost = estimate_cost("unknown-model-xyz", 1_000_000, 1_000_000)
        # Fallback: $3 input + $15 output = $18
        assert cost == 18.0

    def test_prefix_model_match(self):
        cost = estimate_cost("claude-sonnet-4-20250514-extended", 1000, 500)
        assert cost == 0.0105


# ---------------------------------------------------------------------------
# Unit tests: UsageRecord model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUsageRecordModel:
    async def test_create_usage_record(self, db_session: AsyncSession, session_model: SessionModel):
        rec = UsageRecord(
            session_id=session_model.id,
            model="claude-sonnet-4-20250514",
            input_tokens=1523,
            output_tokens=847,
        )
        db_session.add(rec)
        await db_session.commit()
        await db_session.refresh(rec)

        assert rec.id is not None
        assert isinstance(rec.id, uuid.UUID)
        assert rec.session_id == session_model.id
        assert rec.model == "claude-sonnet-4-20250514"
        assert rec.input_tokens == 1523
        assert rec.output_tokens == 847
        assert rec.created_at is not None

    async def test_query_by_session_id(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        usage_records: list[UsageRecord],
    ):
        from sqlalchemy import select

        result = await db_session.execute(
            select(UsageRecord).where(UsageRecord.session_id == session_model.id)
        )
        rows = result.scalars().all()
        assert len(rows) == 3


# ---------------------------------------------------------------------------
# Integration tests: Usage API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUsageAPI:
    async def test_get_usage_empty(self, client: AsyncClient):
        resp = await client.get("/api/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["records"] == []
        assert data["summary"]["total_requests"] == 0
        assert data["summary"]["total_input_tokens"] == 0
        assert data["summary"]["total_output_tokens"] == 0
        assert data["summary"]["estimated_cost"] == 0

    async def test_get_usage_with_records(
        self,
        client: AsyncClient,
        usage_records: list[UsageRecord],
    ):
        resp = await client.get("/api/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["records"]) == 3
        assert data["summary"]["total_requests"] == 3
        # Total input: 1000 + 2000 + 3000 = 6000
        assert data["summary"]["total_input_tokens"] == 6000
        # Total output: 500 + 1000 + 1500 = 3000
        assert data["summary"]["total_output_tokens"] == 3000
        assert data["summary"]["estimated_cost"] > 0

    async def test_get_usage_filter_by_session_id(
        self,
        client: AsyncClient,
        session_model: SessionModel,
        usage_records: list[UsageRecord],
    ):
        resp = await client.get(f"/api/usage?session_id={session_model.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["records"]) == 3

        # Non-existent session
        resp2 = await client.get(f"/api/usage?session_id={uuid.uuid4()}")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["records"]) == 0

    async def test_get_usage_filter_by_project_id(
        self,
        client: AsyncClient,
        project: Project,
        usage_records: list[UsageRecord],
    ):
        resp = await client.get(f"/api/usage?project_id={project.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["records"]) == 3

    async def test_get_usage_filter_by_date_range(
        self,
        client: AsyncClient,
        usage_records: list[UsageRecord],
    ):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/usage?start_date={today}&end_date={today}")
        assert resp.status_code == 200
        data = resp.json()
        # Only today's record
        assert len(data["records"]) >= 1

    async def test_get_usage_summary(
        self,
        client: AsyncClient,
        usage_records: list[UsageRecord],
    ):
        resp = await client.get("/api/usage/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 3
        assert data["total_input_tokens"] == 6000
        assert data["total_output_tokens"] == 3000
        assert data["estimated_cost"] > 0

    async def test_get_session_usage(
        self,
        client: AsyncClient,
        session_model: SessionModel,
        usage_records: list[UsageRecord],
    ):
        resp = await client.get(f"/api/sessions/{session_model.id}/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 3
        assert data["total_input_tokens"] == 6000
        assert data["total_output_tokens"] == 3000
        assert data["estimated_cost"] > 0

    async def test_usage_record_structure(
        self,
        client: AsyncClient,
        usage_records: list[UsageRecord],
    ):
        resp = await client.get("/api/usage")
        data = resp.json()
        record = data["records"][0]
        assert "id" in record
        assert "session_id" in record
        assert "model" in record
        assert "input_tokens" in record
        assert "output_tokens" in record
        assert "estimated_cost" in record
        assert "created_at" in record


# ---------------------------------------------------------------------------
# Unit tests: Context window lookup
# ---------------------------------------------------------------------------


class TestContextWindowLookup:
    def test_known_model_sonnet(self):
        assert MODEL_CONTEXT_WINDOWS["claude-sonnet-4-20250514"] == 200_000

    def test_known_model_opus(self):
        assert MODEL_CONTEXT_WINDOWS["claude-opus-4-20250514"] == 200_000

    def test_known_model_haiku(self):
        assert MODEL_CONTEXT_WINDOWS["claude-haiku-3-20250307"] == 200_000

    def test_short_alias(self):
        assert MODEL_CONTEXT_WINDOWS["claude-sonnet-4"] == 200_000

    def test_codex_mini(self):
        assert MODEL_CONTEXT_WINDOWS["codex-mini-latest"] == 200_000

    def test_get_context_window_known(self):
        assert get_context_window("claude-sonnet-4-20250514") == 200_000

    def test_get_context_window_unknown_returns_default(self):
        assert get_context_window("totally-unknown-model") == 200_000

    def test_get_context_window_prefix_match(self):
        assert get_context_window("claude-sonnet-4-20250514-extended") == 200_000


# ---------------------------------------------------------------------------
# Unit tests: Context usage function
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestContextUsageFunction:
    async def test_context_usage_with_records(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        usage_records: list[UsageRecord],
    ):
        result = await get_context_usage(db_session, session_model.id)
        # The most recent usage record has input_tokens=1000 (first created,
        # but with the earliest created_at due to timedelta subtraction).
        # Actually record[0] has input_tokens=1000 and created_at=now-0days,
        # record[1] has input_tokens=2000 and created_at=now-1day,
        # record[2] has input_tokens=3000 and created_at=now-2days.
        # Most recent by created_at desc => record[0] with input_tokens=1000.
        assert result["used_tokens"] == 1000
        assert result["context_window"] == 200_000
        assert result["usage_percent"] == 0.5
        assert result["model"] == "claude-sonnet-4-20250514"
        assert result["estimated"] is False

    async def test_context_usage_no_records(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        result = await get_context_usage(db_session, session_model.id)
        assert result["used_tokens"] == 0
        assert result["context_window"] == 200_000
        assert result["usage_percent"] == 0.0
        assert result["estimated"] is False

    async def test_context_usage_nonexistent_session(
        self,
        db_session: AsyncSession,
    ):
        result = await get_context_usage(db_session, uuid.uuid4())
        assert result["used_tokens"] == 0
        assert result["estimated"] is True

    async def test_context_usage_cli_engine(
        self,
        db_session: AsyncSession,
        project: Project,
    ):
        """CLI engines should set estimated=True."""
        sess = SessionModel(
            project_id=project.id,
            name="cli-session",
            engine="claude_code",
            mode="execution",
            status="idle",
            config={"model": "claude-sonnet-4"},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(sess)
        await db_session.commit()
        await db_session.refresh(sess)

        result = await get_context_usage(db_session, sess.id)
        assert result["estimated"] is True
        assert result["used_tokens"] == 0


# ---------------------------------------------------------------------------
# Integration tests: Context usage API endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestContextUsageAPI:
    async def test_get_session_context(
        self,
        client: AsyncClient,
        session_model: SessionModel,
        usage_records: list[UsageRecord],
    ):
        resp = await client.get(f"/api/sessions/{session_model.id}/context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["used_tokens"] == 1000
        assert data["context_window"] == 200_000
        assert data["usage_percent"] == 0.5
        assert data["model"] == "claude-sonnet-4-20250514"
        assert "estimated" in data

    async def test_get_session_context_no_records(
        self,
        client: AsyncClient,
        session_model: SessionModel,
    ):
        resp = await client.get(f"/api/sessions/{session_model.id}/context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["used_tokens"] == 0
        assert data["usage_percent"] == 0.0

    async def test_get_session_context_nonexistent(
        self,
        client: AsyncClient,
    ):
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["used_tokens"] == 0
        assert data["estimated"] is True
