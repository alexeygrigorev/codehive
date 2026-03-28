"""Tests for the Agent API endpoints (GET /api/agent/my-task, POST /api/agent/log,
POST /api/agent/verdict) and build_instructions Task API block."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.orchestrator_service import build_instructions
from codehive.db.models import Base, Event, Issue, IssueLogEntry, Project, Task
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(SQLITE_URL)

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
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
        name="test-project",
        knowledge={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest_asyncio.fixture
async def issue(db_session: AsyncSession, project: Project) -> Issue:
    from codehive.core.issues import create_issue

    return await create_issue(
        db_session,
        project_id=project.id,
        title="Test Issue",
        description="Test description",
        acceptance_criteria="- Must pass tests\n- Must be clean",
    )


@pytest_asyncio.fixture
async def task(db_session: AsyncSession, project: Project) -> Task:
    """Create an orchestrator session and a task bound to it."""
    orch_session = SessionModel(
        project_id=project.id,
        name="orchestrator",
        engine="claude_code",
        mode="orchestrator",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(orch_session)
    await db_session.commit()
    await db_session.refresh(orch_session)

    t = Task(
        session_id=orch_session.id,
        title="Implement feature X",
        instructions="Write the code and tests",
        pipeline_status="implementing",
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


@pytest_asyncio.fixture
async def agent_session(
    db_session: AsyncSession,
    project: Project,
    task: Task,
    issue: Issue,
) -> SessionModel:
    """Create an agent session bound to task and issue."""
    s = SessionModel(
        project_id=project.id,
        name="swe-implementing",
        engine="claude_code",
        mode="execution",
        role="swe",
        status="executing",
        config={},
        task_id=task.id,
        issue_id=issue.id,
        pipeline_step="implementing",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with the DB session overridden."""
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /api/agent/my-task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetMyTask:
    async def test_returns_task_details(
        self, client: AsyncClient, agent_session: SessionModel, task: Task, issue: Issue
    ):
        resp = await client.get(
            "/api/agent/my-task",
            headers={"X-Session-Id": str(agent_session.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == str(task.id)
        assert data["title"] == "Implement feature X"
        assert data["instructions"] == "Write the code and tests"
        assert data["pipeline_step"] == "implementing"
        assert data["issue_id"] == str(issue.id)
        assert data["issue_description"] == "Test description"
        assert data["acceptance_criteria"] == "- Must pass tests\n- Must be clean"

    async def test_task_without_issue(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, task: Task
    ):
        """Session bound to task but no issue -- issue fields should be null."""
        s = SessionModel(
            project_id=project.id,
            name="swe-no-issue",
            engine="claude_code",
            mode="execution",
            role="swe",
            status="executing",
            config={},
            task_id=task.id,
            issue_id=None,
            pipeline_step="implementing",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        resp = await client.get(
            "/api/agent/my-task",
            headers={"X-Session-Id": str(s.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == str(task.id)
        assert data["issue_id"] is None
        assert data["issue_description"] is None
        assert data["acceptance_criteria"] is None

    async def test_no_bound_task_returns_404(
        self, client: AsyncClient, db_session: AsyncSession, project: Project
    ):
        """Session exists but has no bound task."""
        s = SessionModel(
            project_id=project.id,
            name="standalone",
            engine="claude_code",
            mode="auto",
            status="idle",
            config={},
            task_id=None,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        resp = await client.get(
            "/api/agent/my-task",
            headers={"X-Session-Id": str(s.id)},
        )
        assert resp.status_code == 404
        assert "no bound task" in resp.json()["detail"]

    async def test_nonexistent_session_returns_404(self, client: AsyncClient):
        resp = await client.get(
            "/api/agent/my-task",
            headers={"X-Session-Id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404
        assert "Session not found" in resp.json()["detail"]

    async def test_missing_header_returns_422(self, client: AsyncClient):
        resp = await client.get("/api/agent/my-task")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/agent/log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPostLog:
    async def test_creates_log_entry(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        agent_session: SessionModel,
        issue: Issue,
    ):
        resp = await client.post(
            "/api/agent/log",
            headers={"X-Session-Id": str(agent_session.id)},
            json={"content": "Running unit tests... 12 passed, 0 failed"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert "id" in data

        # Verify entry in DB
        result = await db_session.execute(
            select(IssueLogEntry).where(IssueLogEntry.issue_id == issue.id)
        )
        entries = list(result.scalars().all())
        assert len(entries) == 1
        assert entries[0].content == "Running unit tests... 12 passed, 0 failed"

    async def test_log_entry_uses_session_role(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        agent_session: SessionModel,
        issue: Issue,
    ):
        resp = await client.post(
            "/api/agent/log",
            headers={"X-Session-Id": str(agent_session.id)},
            json={"content": "test log"},
        )
        assert resp.status_code == 201

        result = await db_session.execute(
            select(IssueLogEntry).where(IssueLogEntry.issue_id == issue.id)
        )
        entry = result.scalars().first()
        assert entry is not None
        assert entry.agent_role == "swe"  # matches agent_session.role

    async def test_no_linked_issue_returns_404(
        self, client: AsyncClient, db_session: AsyncSession, project: Project, task: Task
    ):
        s = SessionModel(
            project_id=project.id,
            name="no-issue-session",
            engine="claude_code",
            mode="execution",
            role="qa",
            status="executing",
            config={},
            task_id=task.id,
            issue_id=None,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        resp = await client.post(
            "/api/agent/log",
            headers={"X-Session-Id": str(s.id)},
            json={"content": "test log"},
        )
        assert resp.status_code == 404
        assert "no linked issue" in resp.json()["detail"]

    async def test_empty_content_returns_422(
        self, client: AsyncClient, agent_session: SessionModel
    ):
        resp = await client.post(
            "/api/agent/log",
            headers={"X-Session-Id": str(agent_session.id)},
            json={"content": "   "},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/agent/verdict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPostVerdict:
    async def test_submit_pass_verdict(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        agent_session: SessionModel,
    ):
        resp = await client.post(
            "/api/agent/verdict",
            headers={"X-Session-Id": str(agent_session.id)},
            json={"verdict": "PASS", "feedback": "All tests pass"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"

        # Verify event in DB
        result = await db_session.execute(
            select(Event).where(Event.session_id == agent_session.id, Event.type == "verdict")
        )
        event = result.scalars().first()
        assert event is not None
        assert event.data["verdict"] == "PASS"
        assert event.data["feedback"] == "All tests pass"

    async def test_verdict_infers_role_from_session(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        agent_session: SessionModel,
    ):
        resp = await client.post(
            "/api/agent/verdict",
            headers={"X-Session-Id": str(agent_session.id)},
            json={"verdict": "PASS"},
        )
        assert resp.status_code == 200

        result = await db_session.execute(
            select(Event).where(Event.session_id == agent_session.id, Event.type == "verdict")
        )
        event = result.scalars().first()
        assert event is not None
        assert event.data["role"] == "swe"  # inferred from session

    async def test_verdict_infers_task_id_from_session(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        agent_session: SessionModel,
        task: Task,
    ):
        resp = await client.post(
            "/api/agent/verdict",
            headers={"X-Session-Id": str(agent_session.id)},
            json={"verdict": "FAIL", "feedback": "broken"},
        )
        assert resp.status_code == 200

        result = await db_session.execute(
            select(Event).where(Event.session_id == agent_session.id, Event.type == "verdict")
        )
        event = result.scalars().first()
        assert event is not None
        assert event.data["task_id"] == str(task.id)

    async def test_verdict_with_evidence_and_criteria(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        agent_session: SessionModel,
    ):
        resp = await client.post(
            "/api/agent/verdict",
            headers={"X-Session-Id": str(agent_session.id)},
            json={
                "verdict": "PASS",
                "feedback": "All good",
                "evidence": [{"type": "test_output", "content": "14 passed"}],
                "criteria_results": [
                    {"criterion": "Health returns 200", "result": "PASS"},
                    {"criterion": "Version present", "result": "PASS"},
                ],
            },
        )
        assert resp.status_code == 200

        result = await db_session.execute(
            select(Event).where(Event.session_id == agent_session.id, Event.type == "verdict")
        )
        event = result.scalars().first()
        assert event is not None
        assert len(event.data["evidence"]) == 1
        assert len(event.data["criteria_results"]) == 2

    async def test_invalid_verdict_returns_422(
        self, client: AsyncClient, agent_session: SessionModel
    ):
        resp = await client.post(
            "/api/agent/verdict",
            headers={"X-Session-Id": str(agent_session.id)},
            json={"verdict": "MAYBE"},
        )
        assert resp.status_code == 422

    async def test_all_verdict_values_accepted(
        self, client: AsyncClient, agent_session: SessionModel
    ):
        for v in ("PASS", "FAIL", "ACCEPT", "REJECT"):
            resp = await client.post(
                "/api/agent/verdict",
                headers={"X-Session-Id": str(agent_session.id)},
                json={"verdict": v},
            )
            assert resp.status_code == 200, f"Verdict {v} should be accepted"


# ---------------------------------------------------------------------------
# build_instructions includes Task API block
# ---------------------------------------------------------------------------


class TestBuildInstructionsTaskAPI:
    def test_with_session_id(self):
        sid = str(uuid.uuid4())
        text = build_instructions(
            "implementing",
            "Feature X",
            "Do the work",
            session_id=sid,
        )
        assert "## Task API" in text
        assert sid in text
        assert "curl" in text
        assert "/api/agent/my-task" in text
        assert "/api/agent/log" in text
        assert "/api/agent/verdict" in text

    def test_without_session_id(self):
        text = build_instructions(
            "implementing",
            "Feature X",
            "Do the work",
        )
        assert "## Task API" not in text

    def test_custom_base_url(self):
        sid = str(uuid.uuid4())
        text = build_instructions(
            "testing",
            "Test X",
            None,
            session_id=sid,
            api_base_url="https://codehive.example.com",
        )
        assert "https://codehive.example.com/api/agent/my-task" in text

    def test_default_base_url(self):
        sid = str(uuid.uuid4())
        text = build_instructions(
            "grooming",
            "Groom X",
            None,
            session_id=sid,
        )
        assert "http://localhost:7433/api/agent/my-task" in text
