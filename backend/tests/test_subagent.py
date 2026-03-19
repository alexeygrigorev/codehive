"""Tests for sub-agent spawning, lifecycle, report validation, and API."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import event
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
from codehive.core.subagent import InvalidEngineError, InvalidReportError, SubAgentManager
from codehive.db.models import Base, Project
from codehive.db.models import Session as SessionModel
from codehive.engine.tools.spawn_subagent import VALID_ENGINE_TYPES
from codehive.engine.orchestrator import ORCHESTRATOR_ALLOWED_TOOLS
from codehive.engine.zai_engine import ZaiEngine, TOOL_DEFINITIONS
from codehive.execution.diff import DiffService
from codehive.execution.file_ops import FileOps
from codehive.execution.git_ops import GitOps
from codehive.execution.shell import ShellRunner

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


@pytest_asyncio.fixture
async def parent_session_member(
    parent_session: SessionModel,
    client: AsyncClient,
    db_session: AsyncSession,
) -> SessionModel:
    """Ensure the test user is an owner of the workspace for API tests."""
    return parent_session


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
        engine = ZaiEngine(
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
            engine=None,
            initial_message=None,
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
        parent_session_member: SessionModel,
    ):
        # Create 2 child sessions
        await create_session(
            db_session,
            project_id=project.id,
            name="child-1",
            engine="native",
            mode="execution",
            parent_session_id=parent_session_member.id,
        )
        await create_session(
            db_session,
            project_id=project.id,
            name="child-2",
            engine="native",
            mode="execution",
            parent_session_id=parent_session_member.id,
        )

        resp = await client.get(f"/api/sessions/{parent_session_member.id}/subagents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        for item in data:
            assert "id" in item
            assert "name" in item
            assert "status" in item
            assert item["parent_session_id"] == str(parent_session_member.id)

    async def test_list_subagents_empty_200(
        self,
        client: AsyncClient,
        parent_session_member: SessionModel,
    ):
        resp = await client.get(f"/api/sessions/{parent_session_member.id}/subagents")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_subagents_404(self, client: AsyncClient):
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/subagents")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Unit: SubAgentManager engine selection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubAgentManagerEngineSelection:
    async def test_spawn_without_engine_inherits_parent(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        """spawn_subagent() without engine parameter: child inherits parent's engine."""
        manager = SubAgentManager()
        result = await manager.spawn_subagent(
            db_session,
            parent_session_id=parent_session.id,
            mission="Inherit engine",
            role="swe",
            scope=["a.py"],
        )
        child_id = uuid.UUID(result["child_session_id"])
        child = await get_session(db_session, child_id)
        assert child is not None
        assert child.engine == parent_session.engine
        assert result["engine"] == parent_session.engine

    async def test_spawn_with_claude_code_engine(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        """spawn_subagent() with engine='claude_code': child has claude_code engine."""
        manager = SubAgentManager()
        result = await manager.spawn_subagent(
            db_session,
            parent_session_id=parent_session.id,
            mission="Use claude_code",
            role="swe",
            scope=["b.py"],
            engine="claude_code",
        )
        child_id = uuid.UUID(result["child_session_id"])
        child = await get_session(db_session, child_id)
        assert child is not None
        assert child.engine == "claude_code"
        assert result["engine"] == "claude_code"

    async def test_spawn_with_codex_cli_engine(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        """spawn_subagent() with engine='codex_cli': child has codex_cli engine."""
        manager = SubAgentManager()
        result = await manager.spawn_subagent(
            db_session,
            parent_session_id=parent_session.id,
            mission="Use codex_cli",
            role="swe",
            scope=[],
            engine="codex_cli",
        )
        child_id = uuid.UUID(result["child_session_id"])
        child = await get_session(db_session, child_id)
        assert child is not None
        assert child.engine == "codex_cli"

    async def test_spawn_with_invalid_engine_raises(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        """spawn_subagent() with invalid engine: raises InvalidEngineError."""
        manager = SubAgentManager()
        with pytest.raises(InvalidEngineError, match="Unknown engine 'nonexistent_engine'"):
            await manager.spawn_subagent(
                db_session,
                parent_session_id=parent_session.id,
                mission="Bad engine",
                role="swe",
                scope=[],
                engine="nonexistent_engine",
            )

    async def test_spawn_event_includes_engine(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        """The subagent.spawned event includes the engine field."""
        bus = _make_event_bus_mock()
        manager = SubAgentManager(event_bus=bus)
        await manager.spawn_subagent(
            db_session,
            parent_session_id=parent_session.id,
            mission="Engine event",
            role="swe",
            scope=[],
            engine="gemini_cli",
        )
        call_args = bus.publish.call_args
        event_data = call_args[0][3]
        assert event_data["engine"] == "gemini_cli"


# ---------------------------------------------------------------------------
# Unit: spawn_subagent tool schema -- engine and initial_message
# ---------------------------------------------------------------------------


class TestSpawnSubagentToolSchemaNew:
    def test_engine_property_in_schema(self):
        """Tool schema includes 'engine' as optional string property."""
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "spawn_subagent")
        props = tool["input_schema"]["properties"]
        assert "engine" in props
        assert props["engine"]["type"] == "string"
        # engine should NOT be required
        assert "engine" not in tool["input_schema"]["required"]

    def test_initial_message_property_in_schema(self):
        """Tool schema includes 'initial_message' as optional string property."""
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "spawn_subagent")
        props = tool["input_schema"]["properties"]
        assert "initial_message" in props
        assert props["initial_message"]["type"] == "string"
        assert "initial_message" not in tool["input_schema"]["required"]


# ---------------------------------------------------------------------------
# Unit: spawn_subagent tool dispatch -- engine and initial_message params
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSpawnSubagentToolDispatchNew:
    async def test_dispatch_passes_engine_param(self, tmp_path: Path):
        """Tool dispatch passes engine to SubAgentManager."""
        client_mock = AsyncMock()
        event_bus = AsyncMock()
        engine = ZaiEngine(
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
            "mission": "test",
            "role": "swe",
            "status": "idle",
            "engine": "claude_code",
        }
        engine._subagent_manager = AsyncMock()
        engine._subagent_manager.spawn_subagent = AsyncMock(return_value=mock_result)

        db_mock = AsyncMock()
        session_id = uuid.uuid4()

        result = await engine._execute_tool(
            "spawn_subagent",
            {
                "mission": "test",
                "role": "swe",
                "scope": [],
                "engine": "claude_code",
            },
            session_id=session_id,
            db=db_mock,
        )

        engine._subagent_manager.spawn_subagent.assert_called_once_with(
            db_mock,
            parent_session_id=session_id,
            mission="test",
            role="swe",
            scope=[],
            engine="claude_code",
            initial_message=None,
            config=None,
        )
        assert not result.get("is_error", False)

    async def test_dispatch_passes_initial_message(self, tmp_path: Path):
        """Tool dispatch passes initial_message to SubAgentManager."""
        client_mock = AsyncMock()
        event_bus = AsyncMock()
        engine = ZaiEngine(
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
            "mission": "test",
            "role": "swe",
            "status": "idle",
            "engine": "native",
            "response": "Done!",
        }
        engine._subagent_manager = AsyncMock()
        engine._subagent_manager.spawn_subagent = AsyncMock(return_value=mock_result)

        db_mock = AsyncMock()
        session_id = uuid.uuid4()

        result = await engine._execute_tool(
            "spawn_subagent",
            {
                "mission": "test",
                "role": "swe",
                "scope": [],
                "initial_message": "Do the thing",
            },
            session_id=session_id,
            db=db_mock,
        )

        call_kwargs = engine._subagent_manager.spawn_subagent.call_args
        assert call_kwargs[1]["initial_message"] == "Do the thing"
        assert not result.get("is_error", False)
        assert "Done!" in result["content"]

    async def test_dispatch_invalid_engine_returns_error(self, tmp_path: Path):
        """Tool dispatch returns error for invalid engine (via SubAgentManager)."""
        client_mock = AsyncMock()
        event_bus = AsyncMock()
        engine = ZaiEngine(
            client=client_mock,
            event_bus=event_bus,
            file_ops=FileOps(tmp_path),
            shell_runner=ShellRunner(),
            git_ops=GitOps(tmp_path),
            diff_service=DiffService(),
        )
        engine._subagent_manager = AsyncMock()
        engine._subagent_manager.spawn_subagent = AsyncMock(
            side_effect=InvalidEngineError("Unknown engine 'bad'")
        )

        db_mock = AsyncMock()
        session_id = uuid.uuid4()

        result = await engine._execute_tool(
            "spawn_subagent",
            {"mission": "test", "role": "swe", "scope": [], "engine": "bad"},
            session_id=session_id,
            db=db_mock,
        )

        assert result["is_error"] is True
        assert "Unknown engine" in result["content"]


# ---------------------------------------------------------------------------
# Integration: SubAgentManager with initial message (mocked engine)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSubAgentManagerInitialMessage:
    async def test_spawn_with_initial_message_calls_engine(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        """spawn_subagent with initial_message builds engine and sends message."""
        create_session_called = False
        send_message_calls: list[tuple[Any, ...]] = []

        class FakeEngine:
            async def create_session(self, session_id: uuid.UUID) -> None:
                nonlocal create_session_called
                create_session_called = True

            async def send_message(self, session_id: uuid.UUID, message: str, **kwargs: Any) -> Any:
                send_message_calls.append((session_id, message))
                yield {
                    "type": "message.created",
                    "role": "assistant",
                    "content": "Hello from child",
                }

        fake_engine = FakeEngine()

        async def mock_builder(config: dict, engine_type: str) -> Any:
            return fake_engine

        manager = SubAgentManager(engine_builder=mock_builder)
        result = await manager.spawn_subagent(
            db_session,
            parent_session_id=parent_session.id,
            mission="Test initial msg",
            role="swe",
            scope=[],
            initial_message="Do something",
        )

        assert result["response"] == "Hello from child"
        assert create_session_called
        assert len(send_message_calls) == 1
        assert send_message_calls[0][1] == "Do something"

    async def test_spawn_without_initial_message_no_engine_built(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        """spawn_subagent without initial_message does not build engine."""
        builder_called = False

        async def mock_builder(config: dict, engine_type: str) -> Any:
            nonlocal builder_called
            builder_called = True
            return AsyncMock()

        manager = SubAgentManager(engine_builder=mock_builder)
        result = await manager.spawn_subagent(
            db_session,
            parent_session_id=parent_session.id,
            mission="No msg",
            role="swe",
            scope=[],
        )

        assert not builder_called
        assert "response" not in result

    async def test_spawn_with_initial_message_engine_crash(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        """spawn_subagent with initial_message and engine crash returns error."""

        async def failing_builder(config: dict, engine_type: str) -> Any:
            raise RuntimeError("Engine build failed")

        manager = SubAgentManager(engine_builder=failing_builder)
        result = await manager.spawn_subagent(
            db_session,
            parent_session_id=parent_session.id,
            mission="Crash test",
            role="swe",
            scope=[],
            initial_message="Try this",
        )

        assert "error building engine" in result["response"]
        # Child session should still have been created
        child_id = uuid.UUID(result["child_session_id"])
        child = await get_session(db_session, child_id)
        assert child is not None

    async def test_spawn_with_initial_message_send_crash(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        """spawn_subagent where send_message raises returns error in response."""
        mock_engine = AsyncMock()
        mock_engine.create_session = AsyncMock()
        mock_engine.send_message = AsyncMock(side_effect=RuntimeError("LLM error"))

        async def mock_builder(config: dict, engine_type: str) -> Any:
            return mock_engine

        manager = SubAgentManager(engine_builder=mock_builder)
        result = await manager.spawn_subagent(
            db_session,
            parent_session_id=parent_session.id,
            mission="Send crash",
            role="swe",
            scope=[],
            initial_message="Trigger error",
        )

        assert "error executing initial message" in result["response"]

    async def test_spawn_no_engine_builder_returns_message(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        """spawn_subagent with initial_message but no engine_builder returns info message."""
        manager = SubAgentManager()  # no engine_builder
        result = await manager.spawn_subagent(
            db_session,
            parent_session_id=parent_session.id,
            mission="No builder",
            role="swe",
            scope=[],
            initial_message="hello",
        )

        assert "engine_builder not configured" in result["response"]

    async def test_spawn_inherits_project_root(self, db_session: AsyncSession, project: Project):
        """Child session config inherits project_root from parent."""
        parent = await create_session(
            db_session,
            project_id=project.id,
            name="parent-with-root",
            engine="native",
            mode="execution",
            config={"project_root": "/home/user/myproject"},
        )
        manager = SubAgentManager()
        result = await manager.spawn_subagent(
            db_session,
            parent_session_id=parent.id,
            mission="Inherit root",
            role="swe",
            scope=[],
            engine="claude_code",
        )
        child_id = uuid.UUID(result["child_session_id"])
        child = await get_session(db_session, child_id)
        assert child is not None
        assert child.config["project_root"] == "/home/user/myproject"


# ---------------------------------------------------------------------------
# Unit: VALID_ENGINE_TYPES constant
# ---------------------------------------------------------------------------


class TestValidEngineTypes:
    def test_contains_expected_engines(self):
        expected = {"native", "claude_code", "codex_cli", "copilot_cli", "gemini_cli", "codex"}
        assert VALID_ENGINE_TYPES == expected


# ---------------------------------------------------------------------------
# Helper: async iterator for mock engine
# ---------------------------------------------------------------------------


async def _async_iter(items: list[Any]) -> Any:
    """Create an async iterator from a list for mocking send_message."""
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# Unit: get_subsession_result -- completed with report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetSubsessionResult:
    async def test_completed_with_report(
        self, db_session: AsyncSession, project: Project, parent_session: SessionModel
    ):
        """Completed subsession with a stored report returns full structured report."""
        bus = _make_event_bus_mock()

        # Make get_events return a fake report event
        fake_report_data = {
            "status": "completed",
            "summary": "Added health check endpoint",
            "files_changed": ["api/health.py"],
            "tests": {"added": 2, "passing": 2},
            "warnings": [],
        }

        class FakeEvent:
            def __init__(self, data: dict):
                self.data = data

        bus.get_events = AsyncMock(return_value=[FakeEvent(fake_report_data)])

        manager = SubAgentManager(event_bus=bus)
        child = await create_session(
            db_session,
            project_id=project.id,
            name="child-completed",
            engine="native",
            mode="execution",
            parent_session_id=parent_session.id,
        )
        # Set child status to completed
        child.status = "completed"
        await db_session.commit()

        result = await manager.get_result(
            db_session,
            child_session_id=child.id,
            parent_session_id=parent_session.id,
        )
        assert result["status"] == "completed"
        assert result["summary"] == "Added health check endpoint"
        assert result["files_changed"] == ["api/health.py"]
        assert result["tests"] == {"added": 2, "passing": 2}

    async def test_running_subsession(
        self, db_session: AsyncSession, project: Project, parent_session: SessionModel
    ):
        """Running subsession returns status with event count."""
        bus = _make_event_bus_mock()
        bus.get_events = AsyncMock(return_value=[object(), object(), object()])

        manager = SubAgentManager(event_bus=bus)
        child = await create_session(
            db_session,
            project_id=project.id,
            name="child-running",
            engine="native",
            mode="execution",
            parent_session_id=parent_session.id,
        )
        child.status = "executing"
        await db_session.commit()

        result = await manager.get_result(
            db_session,
            child_session_id=child.id,
            parent_session_id=parent_session.id,
        )
        assert result["status"] == "executing"
        assert result["summary"] is None
        assert "3 events" in result["progress"]

    async def test_failed_subsession_with_last_message(
        self, db_session: AsyncSession, project: Project, parent_session: SessionModel
    ):
        """Failed subsession without report uses last assistant message as summary."""
        bus = _make_event_bus_mock()

        class FakeEvent:
            def __init__(self, data: dict):
                self.data = data

        # First call for report events returns empty, second for messages
        bus.get_events = AsyncMock(
            side_effect=[
                [],  # no subagent.report events
                [
                    FakeEvent({"role": "user", "content": "do something"}),
                    FakeEvent({"role": "assistant", "content": "Error occurred in tests"}),
                ],
            ]
        )

        manager = SubAgentManager(event_bus=bus)
        child = await create_session(
            db_session,
            project_id=project.id,
            name="child-failed",
            engine="native",
            mode="execution",
            parent_session_id=parent_session.id,
        )
        child.status = "failed"
        await db_session.commit()

        result = await manager.get_result(
            db_session,
            child_session_id=child.id,
            parent_session_id=parent_session.id,
        )
        assert result["status"] == "failed"
        assert result["summary"] == "Error occurred in tests"

    async def test_not_child_of_caller(
        self, db_session: AsyncSession, project: Project, parent_session: SessionModel
    ):
        """Session not a child of caller returns error."""
        manager = SubAgentManager()
        # Create an unrelated session (no parent)
        other = await create_session(
            db_session,
            project_id=project.id,
            name="other-session",
            engine="native",
            mode="execution",
        )
        with pytest.raises(ValueError, match="is not a child of the current session"):
            await manager.get_result(
                db_session,
                child_session_id=other.id,
                parent_session_id=parent_session.id,
            )

    async def test_nonexistent_session(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        """Nonexistent session ID raises SessionNotFoundError."""
        manager = SubAgentManager()
        with pytest.raises(SessionNotFoundError):
            await manager.get_result(
                db_session,
                child_session_id=uuid.uuid4(),
                parent_session_id=parent_session.id,
            )


# ---------------------------------------------------------------------------
# Unit: list_subsessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListSubsessions:
    async def test_list_with_three_children(
        self, db_session: AsyncSession, project: Project, parent_session: SessionModel
    ):
        """Session with 3 children returns list of 3 with correct fields."""
        for i, eng in enumerate(["native", "claude_code", "codex_cli"]):
            await create_session(
                db_session,
                project_id=project.id,
                name=f"child-{i}",
                engine=eng,
                mode="execution",
                parent_session_id=parent_session.id,
            )

        manager = SubAgentManager()
        result = await manager.list_subsessions(db_session, parent_session.id)
        assert len(result) == 3
        engines = {r["engine"] for r in result}
        assert engines == {"native", "claude_code", "codex_cli"}
        for item in result:
            assert "id" in item
            assert "name" in item
            assert "engine" in item
            assert "status" in item

    async def test_list_empty(self, db_session: AsyncSession, parent_session: SessionModel):
        """Session with 0 children returns empty list."""
        manager = SubAgentManager()
        result = await manager.list_subsessions(db_session, parent_session.id)
        assert result == []

    async def test_list_correct_engines(
        self, db_session: AsyncSession, project: Project, parent_session: SessionModel
    ):
        """Returns correct engine field per child."""
        await create_session(
            db_session,
            project_id=project.id,
            name="child-native",
            engine="native",
            mode="execution",
            parent_session_id=parent_session.id,
        )
        await create_session(
            db_session,
            project_id=project.id,
            name="child-claude",
            engine="claude_code",
            mode="execution",
            parent_session_id=parent_session.id,
        )

        manager = SubAgentManager()
        result = await manager.list_subsessions(db_session, parent_session.id)
        by_name = {r["name"]: r for r in result}
        assert by_name["child-native"]["engine"] == "native"
        assert by_name["child-claude"]["engine"] == "claude_code"


# ---------------------------------------------------------------------------
# Unit: tool schemas
# ---------------------------------------------------------------------------


class TestGetSubsessionResultToolSchema:
    def test_tool_present_in_definitions(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "get_subsession_result" in names

    def test_tool_schema_structure(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "get_subsession_result")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "session_id" in schema["properties"]
        assert schema["properties"]["session_id"]["type"] == "string"
        assert "session_id" in schema["required"]


class TestListSubsessionsToolSchema:
    def test_tool_present_in_definitions(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "list_subsessions" in names

    def test_tool_schema_structure(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "list_subsessions")
        schema = tool["input_schema"]
        assert schema["type"] == "object"


# ---------------------------------------------------------------------------
# Integration: tool dispatch in ZaiEngine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetSubsessionResultToolDispatch:
    async def test_dispatch_calls_get_result(self, tmp_path: Path):
        """_execute_tool_direct('get_subsession_result', ...) calls get_result."""
        client_mock = AsyncMock()
        event_bus = AsyncMock()
        engine = ZaiEngine(
            client=client_mock,
            event_bus=event_bus,
            file_ops=FileOps(tmp_path),
            shell_runner=ShellRunner(),
            git_ops=GitOps(tmp_path),
            diff_service=DiffService(),
        )

        mock_result = {
            "status": "completed",
            "summary": "Done",
            "files_changed": ["a.py"],
            "tests": {"added": 1, "passing": 1},
            "warnings": [],
        }
        engine._subagent_manager = AsyncMock()
        engine._subagent_manager.get_result = AsyncMock(return_value=mock_result)

        db_mock = AsyncMock()
        session_id = uuid.uuid4()
        child_id = uuid.uuid4()

        result = await engine._execute_tool_direct(
            "get_subsession_result",
            {"session_id": str(child_id)},
            session_id=session_id,
            db=db_mock,
        )

        engine._subagent_manager.get_result.assert_called_once_with(
            db_mock,
            child_session_id=child_id,
            parent_session_id=session_id,
        )
        assert not result.get("is_error", False)
        assert "completed" in result["content"]


@pytest.mark.asyncio
class TestListSubsessionsToolDispatch:
    async def test_dispatch_calls_list_subsessions(self, tmp_path: Path):
        """_execute_tool_direct('list_subsessions', ...) calls list_subsessions."""
        client_mock = AsyncMock()
        event_bus = AsyncMock()
        engine = ZaiEngine(
            client=client_mock,
            event_bus=event_bus,
            file_ops=FileOps(tmp_path),
            shell_runner=ShellRunner(),
            git_ops=GitOps(tmp_path),
            diff_service=DiffService(),
        )

        mock_result = [
            {"id": str(uuid.uuid4()), "name": "child-1", "engine": "native", "status": "idle"},
        ]
        engine._subagent_manager = AsyncMock()
        engine._subagent_manager.list_subsessions = AsyncMock(return_value=mock_result)

        db_mock = AsyncMock()
        session_id = uuid.uuid4()

        result = await engine._execute_tool_direct(
            "list_subsessions",
            {},
            session_id=session_id,
            db=db_mock,
        )

        engine._subagent_manager.list_subsessions.assert_called_once_with(
            db_mock,
            parent_session_id=session_id,
        )
        assert not result.get("is_error", False)
        assert "child-1" in result["content"]


# ---------------------------------------------------------------------------
# Integration: ORCHESTRATOR_ALLOWED_TOOLS
# ---------------------------------------------------------------------------


class TestOrchestratorAllowedTools:
    def test_get_subsession_result_in_allowed(self):
        assert "get_subsession_result" in ORCHESTRATOR_ALLOWED_TOOLS

    def test_list_subsessions_in_allowed(self):
        assert "list_subsessions" in ORCHESTRATOR_ALLOWED_TOOLS
