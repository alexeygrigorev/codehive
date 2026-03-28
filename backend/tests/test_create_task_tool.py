"""Tests for the create_task tool: schema, orchestrator integration, shared service, events."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.backlog_service import (
    BacklogResult,
    ProjectNotFoundForBacklogError,
    create_backlog_task,
)
from codehive.core.events import LocalEventBus
from codehive.db.models import Base, Event, Issue, Project, Task
from codehive.db.models import Session as SessionModel
from codehive.engine.orchestrator import ORCHESTRATOR_ALLOWED_TOOLS, filter_tools
from codehive.engine.tools.create_task import CREATE_TASK_TOOL

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
        name="test-project",
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
            json={"email": "ct@test.com", "username": "ctuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit: Tool schema validation
# ---------------------------------------------------------------------------


class TestCreateTaskToolSchema:
    def test_name(self):
        assert CREATE_TASK_TOOL["name"] == "create_task"

    def test_title_required(self):
        schema = CREATE_TASK_TOOL["input_schema"]
        assert "title" in schema["required"]

    def test_optional_description(self):
        props = CREATE_TASK_TOOL["input_schema"]["properties"]
        assert "description" in props
        assert "description" not in CREATE_TASK_TOOL["input_schema"]["required"]

    def test_optional_acceptance_criteria(self):
        props = CREATE_TASK_TOOL["input_schema"]["properties"]
        assert "acceptance_criteria" in props
        assert "acceptance_criteria" not in CREATE_TASK_TOOL["input_schema"]["required"]


# ---------------------------------------------------------------------------
# Unit: Orchestrator allowed tools
# ---------------------------------------------------------------------------


class TestOrchestratorAllowedTools:
    def test_create_task_in_allowed_tools(self):
        assert "create_task" in ORCHESTRATOR_ALLOWED_TOOLS

    def test_filter_tools_includes_create_task(self):
        tool_defs = [
            {"name": "read_file"},
            {"name": "edit_file"},
            {"name": "create_task"},
            {"name": "spawn_subagent"},
        ]
        filtered = filter_tools(tool_defs)
        names = {t["name"] for t in filtered}
        assert "create_task" in names
        # edit_file should be excluded (not in orchestrator allowed tools)
        assert "edit_file" not in names


# ---------------------------------------------------------------------------
# Unit: Shared service function
# ---------------------------------------------------------------------------


class TestCreateBacklogTask:
    @pytest.mark.asyncio
    async def test_creates_issue_and_task(self, db_session: AsyncSession, project: Project):
        result = await create_backlog_task(
            db_session,
            project_id=project.id,
            title="Fix sidebar bug",
            description="The sidebar does not refresh",
            acceptance_criteria="- [ ] Sidebar refreshes",
        )

        assert isinstance(result, BacklogResult)
        assert result.pipeline_status == "backlog"

        # Verify Issue was created with status "open"
        issue = await db_session.get(Issue, result.issue_id)
        assert issue is not None
        assert issue.status == "open"
        assert issue.title == "Fix sidebar bug"
        assert issue.description == "The sidebar does not refresh"
        assert issue.acceptance_criteria == "- [ ] Sidebar refreshes"

        # Verify Task was created with pipeline_status "backlog"
        task = await db_session.get(Task, result.task_id)
        assert task is not None
        assert task.pipeline_status == "backlog"
        assert task.title == "Fix sidebar bug"

    @pytest.mark.asyncio
    async def test_title_only(self, db_session: AsyncSession, project: Project):
        """Succeeds with only title (no description, no acceptance_criteria)."""
        result = await create_backlog_task(
            db_session,
            project_id=project.id,
            title="Add dark mode",
        )

        assert result.pipeline_status == "backlog"

        issue = await db_session.get(Issue, result.issue_id)
        assert issue is not None
        assert issue.title == "Add dark mode"
        assert issue.description is None
        assert issue.acceptance_criteria is None

        task = await db_session.get(Task, result.task_id)
        assert task is not None

    @pytest.mark.asyncio
    async def test_nonexistent_project(self, db_session: AsyncSession):
        fake_id = uuid.uuid4()
        with pytest.raises(ProjectNotFoundForBacklogError):
            await create_backlog_task(
                db_session,
                project_id=fake_id,
                title="Will fail",
            )


# ---------------------------------------------------------------------------
# Unit: Event emission
# ---------------------------------------------------------------------------


class TestEventEmission:
    @pytest.mark.asyncio
    async def test_task_created_event_emitted(self, db_session: AsyncSession, project: Project):
        bus = LocalEventBus()

        result = await create_backlog_task(
            db_session,
            project_id=project.id,
            title="Event test task",
            description="Check events",
            event_bus=bus,
        )

        # Verify a task.created event was persisted
        events = await db_session.execute(select(Event).where(Event.type == "task.created"))
        event_list = list(events.scalars().all())
        assert len(event_list) == 1
        ev = event_list[0]
        assert ev.data["task_id"] == str(result.task_id)
        assert ev.data["issue_id"] == str(result.issue_id)
        assert ev.data["pipeline_status"] == "backlog"
        assert ev.data["title"] == "Event test task"

    @pytest.mark.asyncio
    async def test_no_event_without_bus(self, db_session: AsyncSession, project: Project):
        """When no event_bus is provided, no event rows are created."""
        await create_backlog_task(
            db_session,
            project_id=project.id,
            title="No event task",
        )

        events = await db_session.execute(select(Event).where(Event.type == "task.created"))
        assert len(list(events.scalars().all())) == 0


# ---------------------------------------------------------------------------
# Integration: Tool execution in session context
# ---------------------------------------------------------------------------


def _make_engine(event_bus=None):
    """Build a ZaiEngine with mocked dependencies (only _execute_tool_direct is used)."""
    from unittest.mock import MagicMock

    from codehive.engine.zai_engine import ZaiEngine

    engine = ZaiEngine(
        client=AsyncMock(),
        event_bus=event_bus or MagicMock(),
        file_ops=MagicMock(),
        shell_runner=MagicMock(),
        git_ops=MagicMock(),
        diff_service=MagicMock(),
        model="test",
    )
    # Override _event_bus to the passed value so create_backlog_task
    # receives the correct object (or None to skip event emission).
    engine._event_bus = event_bus
    return engine


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_create_task_tool_handler(
        self, db_session: AsyncSession, project: Project, orch_session: SessionModel
    ):
        """Simulate calling create_task through the engine's _execute_tool_direct."""
        engine = _make_engine()

        result = await engine._execute_tool_direct(
            "create_task",
            {"title": "Fix bug", "description": "Details about the bug"},
            session_id=orch_session.id,
            db=db_session,
        )

        assert "is_error" not in result or result.get("is_error") is not True
        data = json.loads(result["content"])
        assert "issue_id" in data
        assert "task_id" in data
        assert data["pipeline_status"] == "backlog"

        # Verify rows exist in DB
        issue = await db_session.get(Issue, uuid.UUID(data["issue_id"]))
        assert issue is not None
        assert issue.status == "open"

        task = await db_session.get(Task, uuid.UUID(data["task_id"]))
        assert task is not None
        assert task.pipeline_status == "backlog"

    @pytest.mark.asyncio
    async def test_create_task_tool_no_session(self):
        """Tool returns error when session_id is None."""
        engine = _make_engine()

        result = await engine._execute_tool_direct(
            "create_task",
            {"title": "Will fail"},
            session_id=None,
            db=None,
        )

        assert result["is_error"] is True
        assert "requires an active session" in result["content"]

    @pytest.mark.asyncio
    async def test_create_task_tool_with_acceptance_criteria(
        self, db_session: AsyncSession, project: Project, orch_session: SessionModel
    ):
        engine = _make_engine()

        result = await engine._execute_tool_direct(
            "create_task",
            {
                "title": "Add feature X",
                "description": "Full description",
                "acceptance_criteria": "- [ ] Criterion 1\n- [ ] Criterion 2",
            },
            session_id=orch_session.id,
            db=db_session,
        )

        data = json.loads(result["content"])
        issue = await db_session.get(Issue, uuid.UUID(data["issue_id"]))
        assert issue.acceptance_criteria == "- [ ] Criterion 1\n- [ ] Criterion 2"


# ---------------------------------------------------------------------------
# Integration: API endpoint still works (regression)
# ---------------------------------------------------------------------------


class TestAddTaskEndpointRegression:
    @pytest.mark.asyncio
    async def test_add_task_endpoint(self, client: AsyncClient, project: Project):
        resp = await client.post(
            "/api/orchestrator/add-task",
            json={
                "project_id": str(project.id),
                "title": "Regression test task",
                "description": "Testing refactored endpoint",
                "acceptance_criteria": "- Works correctly",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["pipeline_status"] == "backlog"
        assert "issue_id" in data
        assert "task_id" in data

    @pytest.mark.asyncio
    async def test_add_task_endpoint_not_found(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            "/api/orchestrator/add-task",
            json={
                "project_id": fake_id,
                "title": "Will fail",
            },
        )
        assert resp.status_code == 404
