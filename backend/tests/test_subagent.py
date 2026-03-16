"""Tests for sub-agent spawning, lifecycle, report validation, and API."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import JSON, MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.api.schemas.session import SubAgentReport
from codehive.core.session import (
    SessionNotFoundError,
    create_session,
    get_session,
    get_session_tree,
    list_child_sessions,
)
from codehive.core.subagent import InvalidReportError, SubAgentManager
from codehive.db.models import Base, Project, Workspace
from codehive.db.models import Session as SessionModel
from codehive.engine.native import NativeEngine, TOOL_DEFINITIONS
from codehive.execution.diff import DiffService
from codehive.execution.file_ops import FileOps
from codehive.execution.git_ops import GitOps
from codehive.execution.shell import ShellRunner

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


def _sqlite_compatible_metadata() -> MetaData:
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
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    sqlite_metadata = _sqlite_compatible_metadata()
    async with engine.begin() as conn:
        await conn.run_sync(sqlite_metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(sqlite_metadata.drop_all)
    await engine.dispose()


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
async def parent_session(db_session: AsyncSession, project: Project) -> SessionModel:
    return await create_session(
        db_session,
        project_id=project.id,
        name="parent-session",
        engine="native",
        mode="execution",
    )


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register a test user and include auth headers
        resp = await ac.post(
            "/api/auth/register",
            json={"email": "test@test.com", "username": "testuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


def _make_event_bus_mock() -> AsyncMock:
    """Create a mock EventBus with a publish method."""
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


# ---------------------------------------------------------------------------
# Unit: SubAgentManager.spawn_subagent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubAgentManagerSpawn:
    async def test_spawn_creates_child_session(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        manager = SubAgentManager()
        result = await manager.spawn_subagent(
            db_session,
            parent_session_id=parent_session.id,
            mission="Implement feature X",
            role="swe",
            scope=["src/main.py", "src/utils.py"],
        )
        assert "child_session_id" in result
        child_id = uuid.UUID(result["child_session_id"])
        child = await get_session(db_session, child_id)
        assert child is not None
        assert child.parent_session_id == parent_session.id
        assert child.project_id == parent_session.project_id
        assert child.engine == parent_session.engine
        assert child.status == "idle"
        assert child.config["mission"] == "Implement feature X"
        assert child.config["role"] == "swe"
        assert child.config["scope"] == ["src/main.py", "src/utils.py"]

    async def test_spawn_nonexistent_parent_raises(self, db_session: AsyncSession):
        manager = SubAgentManager()
        with pytest.raises(SessionNotFoundError):
            await manager.spawn_subagent(
                db_session,
                parent_session_id=uuid.uuid4(),
                mission="test",
                role="swe",
                scope=[],
            )

    async def test_spawn_emits_event(self, db_session: AsyncSession, parent_session: SessionModel):
        bus = _make_event_bus_mock()
        manager = SubAgentManager(event_bus=bus)
        result = await manager.spawn_subagent(
            db_session,
            parent_session_id=parent_session.id,
            mission="Fix bug Y",
            role="tester",
            scope=["tests/"],
        )
        bus.publish.assert_called_once()
        call_args = bus.publish.call_args
        assert call_args[0][2] == "subagent.spawned"
        event_data = call_args[0][3]
        assert event_data["parent_session_id"] == str(parent_session.id)
        assert event_data["child_session_id"] == result["child_session_id"]
        assert event_data["mission"] == "Fix bug Y"
        assert event_data["role"] == "tester"


# ---------------------------------------------------------------------------
# Unit: SubAgentManager.collect_report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubAgentManagerCollectReport:
    async def test_valid_report_accepted(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        manager = SubAgentManager()
        report = {
            "status": "completed",
            "summary": "All done",
            "files_changed": ["a.py", "b.py"],
            "tests": {"added": 3, "passing": 3},
            "warnings": [],
        }
        validated = await manager.collect_report(db_session, parent_session.id, report)
        assert validated["status"] == "completed"
        assert validated["summary"] == "All done"

    async def test_invalid_status_raises(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        manager = SubAgentManager()
        report = {
            "status": "unknown",
            "summary": "Bad",
            "files_changed": [],
            "tests": {"added": 0, "passing": 0},
            "warnings": [],
        }
        with pytest.raises(InvalidReportError, match="Invalid status"):
            await manager.collect_report(db_session, parent_session.id, report)

    async def test_empty_summary_raises(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        manager = SubAgentManager()
        report = {
            "status": "completed",
            "summary": "",
            "files_changed": [],
            "tests": {"added": 0, "passing": 0},
            "warnings": [],
        }
        with pytest.raises(InvalidReportError, match="summary must be a non-empty string"):
            await manager.collect_report(db_session, parent_session.id, report)

    async def test_missing_tests_key_raises(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        manager = SubAgentManager()
        report = {
            "status": "failed",
            "summary": "Something went wrong",
            "files_changed": [],
            "warnings": [],
        }
        with pytest.raises(InvalidReportError, match="tests must be a dict"):
            await manager.collect_report(db_session, parent_session.id, report)

    async def test_valid_report_emits_event(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        bus = _make_event_bus_mock()
        manager = SubAgentManager(event_bus=bus)
        report = {
            "status": "completed",
            "summary": "Done",
            "files_changed": [],
            "tests": {"added": 1, "passing": 1},
            "warnings": ["minor issue"],
        }
        await manager.collect_report(db_session, parent_session.id, report)
        bus.publish.assert_called_once()
        call_args = bus.publish.call_args
        assert call_args[0][2] == "subagent.report"


# ---------------------------------------------------------------------------
# Unit: SubAgentManager.get_subagent_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubAgentManagerGetStatus:
    async def test_get_status_returns_current(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        manager = SubAgentManager()
        status = await manager.get_subagent_status(db_session, parent_session.id)
        assert status == "idle"

    async def test_get_status_nonexistent_raises(self, db_session: AsyncSession):
        manager = SubAgentManager()
        with pytest.raises(SessionNotFoundError):
            await manager.get_subagent_status(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Unit: session.list_child_sessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListChildSessions:
    async def test_list_with_children(
        self, db_session: AsyncSession, project: Project, parent_session: SessionModel
    ):
        await create_session(
            db_session,
            project_id=project.id,
            name="child-1",
            engine="native",
            mode="execution",
            parent_session_id=parent_session.id,
        )
        await create_session(
            db_session,
            project_id=project.id,
            name="child-2",
            engine="native",
            mode="execution",
            parent_session_id=parent_session.id,
        )
        children = await list_child_sessions(db_session, parent_session.id)
        assert len(children) == 2
        names = {c.name for c in children}
        assert names == {"child-1", "child-2"}

    async def test_list_no_children(self, db_session: AsyncSession, parent_session: SessionModel):
        children = await list_child_sessions(db_session, parent_session.id)
        assert children == []

    async def test_list_nonexistent_parent_raises(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await list_child_sessions(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Unit: session.get_session_tree
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetSessionTree:
    async def test_tree_with_children(
        self, db_session: AsyncSession, project: Project, parent_session: SessionModel
    ):
        await create_session(
            db_session,
            project_id=project.id,
            name="child-1",
            engine="native",
            mode="execution",
            parent_session_id=parent_session.id,
        )
        await create_session(
            db_session,
            project_id=project.id,
            name="child-2",
            engine="native",
            mode="execution",
            parent_session_id=parent_session.id,
        )
        tree = await get_session_tree(db_session, parent_session.id)
        assert tree["session"].id == parent_session.id
        assert len(tree["children"]) == 2

    async def test_tree_no_children(self, db_session: AsyncSession, parent_session: SessionModel):
        tree = await get_session_tree(db_session, parent_session.id)
        assert tree["session"].id == parent_session.id
        assert tree["children"] == []


# ---------------------------------------------------------------------------
# Unit: spawn_subagent tool schema
# ---------------------------------------------------------------------------


class TestSpawnSubagentToolSchema:
    def test_tool_present_in_definitions(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "spawn_subagent" in names

    def test_tool_schema_structure(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "spawn_subagent")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        props = schema["properties"]
        assert "mission" in props
        assert props["mission"]["type"] == "string"
        assert "role" in props
        assert props["role"]["type"] == "string"
        assert "scope" in props
        assert props["scope"]["type"] == "array"
        assert "config" in props
        assert props["config"]["type"] == "object"
        assert set(schema["required"]) == {"mission", "role", "scope"}


# ---------------------------------------------------------------------------
# Unit: spawn_subagent tool dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSpawnSubagentToolDispatch:
    async def test_dispatch_calls_subagent_manager(self, tmp_path: Path):
        client_mock = AsyncMock()
        event_bus = AsyncMock()
        engine = NativeEngine(
            client=client_mock,
            event_bus=event_bus,
            file_ops=FileOps(tmp_path),
            shell_runner=ShellRunner(),
            git_ops=GitOps(tmp_path),
            diff_service=DiffService(),
        )

        mock_result = {
            "child_session_id": str(uuid.uuid4()),
            "parent_session_id": str(uuid.uuid4()),
            "mission": "test mission",
            "role": "swe",
            "status": "idle",
        }
        engine._subagent_manager = AsyncMock()
        engine._subagent_manager.spawn_subagent = AsyncMock(return_value=mock_result)

        db_mock = AsyncMock()
        session_id = uuid.uuid4()

        result = await engine._execute_tool(
            "spawn_subagent",
            {"mission": "test mission", "role": "swe", "scope": ["a.py"]},
            session_id=session_id,
            db=db_mock,
        )

        engine._subagent_manager.spawn_subagent.assert_called_once_with(
            db_mock,
            parent_session_id=session_id,
            mission="test mission",
            role="swe",
            scope=["a.py"],
            config=None,
        )
        assert "child_session_id" in result["content"]
        assert not result.get("is_error", False)


# ---------------------------------------------------------------------------
# Unit: SubAgentReport schema validation
# ---------------------------------------------------------------------------


class TestSubAgentReportSchema:
    def test_valid_report(self):
        report = SubAgentReport(
            status="completed",
            summary="All good",
            files_changed=["a.py"],
            tests={"added": 2, "passing": 2},
            warnings=[],
        )
        assert report.status.value == "completed"
        assert report.summary == "All good"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            SubAgentReport(
                status="unknown",
                summary="Bad",
                files_changed=[],
                tests={"added": 0, "passing": 0},
                warnings=[],
            )

    def test_missing_summary_rejected(self):
        with pytest.raises(ValidationError):
            SubAgentReport(
                status="completed",
                files_changed=[],
                tests={"added": 0, "passing": 0},
                warnings=[],
            )


# ---------------------------------------------------------------------------
# Integration: GET /api/sessions/{session_id}/subagents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubagentsEndpoint:
    async def test_list_subagents_200(
        self,
        client: AsyncClient,
        project: Project,
        db_session: AsyncSession,
        parent_session: SessionModel,
    ):
        # Create 2 child sessions
        await create_session(
            db_session,
            project_id=project.id,
            name="child-1",
            engine="native",
            mode="execution",
            parent_session_id=parent_session.id,
        )
        await create_session(
            db_session,
            project_id=project.id,
            name="child-2",
            engine="native",
            mode="execution",
            parent_session_id=parent_session.id,
        )

        resp = await client.get(f"/api/sessions/{parent_session.id}/subagents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        for item in data:
            assert "id" in item
            assert "name" in item
            assert "status" in item
            assert item["parent_session_id"] == str(parent_session.id)

    async def test_list_subagents_empty_200(
        self,
        client: AsyncClient,
        parent_session: SessionModel,
    ):
        resp = await client.get(f"/api/sessions/{parent_session.id}/subagents")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_subagents_404(self, client: AsyncClient):
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/subagents")
        assert resp.status_code == 404
