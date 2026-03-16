"""Tests for agent-to-agent communication: query, send, broadcast, tools, API."""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.agent_comm import AgentCommService
from codehive.core.session import (
    SessionNotFoundError,
    create_session,
)
from codehive.core.task_queue import create_task, transition_task
from codehive.db.models import Base, Event, Project, Workspace
from codehive.db.models import Session as SessionModel
from codehive.engine.native import TOOL_DEFINITIONS, NativeEngine
from codehive.execution.diff import DiffService
from codehive.execution.file_ops import FileOps
from codehive.execution.git_ops import GitOps
from codehive.execution.shell import ShellRunner

# ---------------------------------------------------------------------------
# Fixtures (same SQLite-in-memory pattern as test_subagent.py)
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
        name="orchestrator",
        engine="native",
        mode="execution",
    )


@pytest_asyncio.fixture
async def child_session_a(
    db_session: AsyncSession, project: Project, parent_session: SessionModel
) -> SessionModel:
    return await create_session(
        db_session,
        project_id=project.id,
        name="subagent-swe",
        engine="native",
        mode="execution",
        parent_session_id=parent_session.id,
    )


@pytest_asyncio.fixture
async def child_session_b(
    db_session: AsyncSession, project: Project, parent_session: SessionModel
) -> SessionModel:
    return await create_session(
        db_session,
        project_id=project.id,
        name="subagent-tester",
        engine="native",
        mode="execution",
        parent_session_id=parent_session.id,
    )


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


def _make_event_bus_mock() -> AsyncMock:
    """Create a mock EventBus with a publish method that returns a mock Event."""
    bus = AsyncMock()
    mock_event = AsyncMock()
    mock_event.id = uuid.uuid4()
    bus.publish = AsyncMock(return_value=mock_event)
    return bus


# ---------------------------------------------------------------------------
# Unit: AgentCommService.query_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestQueryAgent:
    async def test_query_existing_session(
        self, db_session: AsyncSession, child_session_a: SessionModel
    ):
        comm = AgentCommService()
        result = await comm.query_agent(db_session, target_session_id=child_session_a.id)
        assert result["session_id"] == str(child_session_a.id)
        assert result["status"] == "idle"
        assert result["mode"] == "execution"
        assert result["name"] == "subagent-swe"
        assert result["current_task"] is None
        assert result["recent_events"] == []

    async def test_query_session_with_running_task(
        self, db_session: AsyncSession, child_session_a: SessionModel
    ):
        task = await create_task(
            db_session,
            session_id=child_session_a.id,
            title="Implement feature X",
        )
        await transition_task(db_session, task.id, "running")

        comm = AgentCommService()
        result = await comm.query_agent(db_session, target_session_id=child_session_a.id)
        assert result["current_task"] is not None
        assert result["current_task"]["id"] == str(task.id)
        assert result["current_task"]["title"] == "Implement feature X"
        assert result["current_task"]["status"] == "running"

    async def test_query_session_no_running_task(
        self, db_session: AsyncSession, child_session_a: SessionModel
    ):
        # Create a pending task (not running)
        await create_task(
            db_session,
            session_id=child_session_a.id,
            title="Pending task",
        )
        comm = AgentCommService()
        result = await comm.query_agent(db_session, target_session_id=child_session_a.id)
        assert result["current_task"] is None

    async def test_query_session_with_events(
        self, db_session: AsyncSession, child_session_a: SessionModel
    ):
        # Manually create events
        for i in range(3):
            ev = Event(
                session_id=child_session_a.id,
                type="file.changed",
                data={"path": f"file{i}.py"},
                created_at=datetime.now(timezone.utc),
            )
            db_session.add(ev)
        await db_session.commit()

        comm = AgentCommService()
        result = await comm.query_agent(db_session, target_session_id=child_session_a.id)
        assert len(result["recent_events"]) == 3
        assert result["recent_events"][0]["type"] == "file.changed"

    async def test_query_with_custom_limit(
        self, db_session: AsyncSession, child_session_a: SessionModel
    ):
        for i in range(5):
            ev = Event(
                session_id=child_session_a.id,
                type="file.changed",
                data={"path": f"file{i}.py"},
                created_at=datetime.now(timezone.utc),
            )
            db_session.add(ev)
        await db_session.commit()

        comm = AgentCommService()
        result = await comm.query_agent(db_session, target_session_id=child_session_a.id, limit=2)
        assert len(result["recent_events"]) == 2

    async def test_query_nonexistent_session(self, db_session: AsyncSession):
        comm = AgentCommService()
        with pytest.raises(SessionNotFoundError):
            await comm.query_agent(db_session, target_session_id=uuid.uuid4())

    async def test_query_publishes_event(
        self,
        db_session: AsyncSession,
        child_session_a: SessionModel,
        parent_session: SessionModel,
    ):
        bus = _make_event_bus_mock()
        comm = AgentCommService(event_bus=bus)
        await comm.query_agent(
            db_session,
            target_session_id=child_session_a.id,
            querying_session_id=parent_session.id,
        )
        bus.publish.assert_called_once()
        call_args = bus.publish.call_args
        assert call_args[0][1] == parent_session.id  # published on querying session
        assert call_args[0][2] == "agent.query"
        assert "queried_session_id" in call_args[0][3]


# ---------------------------------------------------------------------------
# Unit: AgentCommService.send_to_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSendToAgent:
    async def test_send_message_to_existing_session(
        self,
        db_session: AsyncSession,
        parent_session: SessionModel,
        child_session_a: SessionModel,
    ):
        bus = _make_event_bus_mock()
        comm = AgentCommService(event_bus=bus)
        result = await comm.send_to_agent(
            db_session,
            sender_session_id=parent_session.id,
            target_session_id=child_session_a.id,
            message="How is the task going?",
        )
        assert result["target_session_id"] == str(child_session_a.id)
        assert result["message"] == "How is the task going?"
        assert result["event_id"] is not None

    async def test_send_creates_events_on_both_streams(
        self,
        db_session: AsyncSession,
        parent_session: SessionModel,
        child_session_a: SessionModel,
    ):
        bus = _make_event_bus_mock()
        comm = AgentCommService(event_bus=bus)
        await comm.send_to_agent(
            db_session,
            sender_session_id=parent_session.id,
            target_session_id=child_session_a.id,
            message="Hello",
        )
        # Should be called twice: once for target, once for sender (audit)
        assert bus.publish.call_count == 2
        # First call is on target
        first_call = bus.publish.call_args_list[0]
        assert first_call[0][1] == child_session_a.id
        assert first_call[0][2] == "agent.message"
        # Second call is on sender
        second_call = bus.publish.call_args_list[1]
        assert second_call[0][1] == parent_session.id
        assert second_call[0][2] == "agent.message"

    async def test_send_event_data_contains_required_fields(
        self,
        db_session: AsyncSession,
        parent_session: SessionModel,
        child_session_a: SessionModel,
    ):
        bus = _make_event_bus_mock()
        comm = AgentCommService(event_bus=bus)
        await comm.send_to_agent(
            db_session,
            sender_session_id=parent_session.id,
            target_session_id=child_session_a.id,
            message="Test message",
        )
        event_data = bus.publish.call_args_list[0][0][3]
        assert "sender_session_id" in event_data
        assert "message" in event_data
        assert "timestamp" in event_data
        assert event_data["sender_session_id"] == str(parent_session.id)
        assert event_data["message"] == "Test message"

    async def test_send_to_nonexistent_session(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        comm = AgentCommService()
        with pytest.raises(SessionNotFoundError):
            await comm.send_to_agent(
                db_session,
                sender_session_id=parent_session.id,
                target_session_id=uuid.uuid4(),
                message="Hello",
            )

    async def test_send_from_nonexistent_sender(self, db_session: AsyncSession):
        comm = AgentCommService()
        with pytest.raises(SessionNotFoundError):
            await comm.send_to_agent(
                db_session,
                sender_session_id=uuid.uuid4(),
                target_session_id=uuid.uuid4(),
                message="Hello",
            )


# ---------------------------------------------------------------------------
# Unit: AgentCommService.broadcast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBroadcast:
    async def test_broadcast_to_siblings(
        self,
        db_session: AsyncSession,
        parent_session: SessionModel,
        child_session_a: SessionModel,
        child_session_b: SessionModel,
    ):
        bus = _make_event_bus_mock()
        comm = AgentCommService(event_bus=bus)
        recipients = await comm.broadcast(
            db_session,
            sender_session_id=child_session_a.id,
            message="I found a bug",
        )
        # Should send to child_session_b only (not to sender)
        assert len(recipients) == 1
        assert str(child_session_b.id) in recipients

    async def test_broadcast_no_siblings(
        self,
        db_session: AsyncSession,
        project: Project,
        parent_session: SessionModel,
    ):
        # Create a single child - no siblings to send to
        only_child = await create_session(
            db_session,
            project_id=project.id,
            name="lonely-agent",
            engine="native",
            mode="execution",
            parent_session_id=parent_session.id,
        )
        comm = AgentCommService()
        recipients = await comm.broadcast(
            db_session,
            sender_session_id=only_child.id,
            message="Anyone there?",
        )
        assert recipients == []

    async def test_broadcast_no_parent_raises(
        self, db_session: AsyncSession, parent_session: SessionModel
    ):
        # parent_session has no parent_session_id
        comm = AgentCommService()
        with pytest.raises(ValueError, match="no parent session"):
            await comm.broadcast(
                db_session,
                sender_session_id=parent_session.id,
                message="Hello",
            )

    async def test_broadcast_nonexistent_sender_raises(self, db_session: AsyncSession):
        comm = AgentCommService()
        with pytest.raises(SessionNotFoundError):
            await comm.broadcast(
                db_session,
                sender_session_id=uuid.uuid4(),
                message="Hello",
            )


# ---------------------------------------------------------------------------
# Unit: Tool schemas
# ---------------------------------------------------------------------------


class TestToolSchemas:
    def test_query_agent_tool_in_definitions(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "query_agent" in names

    def test_query_agent_tool_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "query_agent")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        props = schema["properties"]
        assert "session_id" in props
        assert props["session_id"]["type"] == "string"
        assert "limit" in props
        assert props["limit"]["type"] == "integer"
        assert schema["required"] == ["session_id"]

    def test_send_to_agent_tool_in_definitions(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "send_to_agent" in names

    def test_send_to_agent_tool_schema(self):
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "send_to_agent")
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        props = schema["properties"]
        assert "session_id" in props
        assert props["session_id"]["type"] == "string"
        assert "message" in props
        assert props["message"]["type"] == "string"
        assert set(schema["required"]) == {"session_id", "message"}


# ---------------------------------------------------------------------------
# Unit: Tool dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestToolDispatch:
    async def test_dispatch_query_agent(self, tmp_path: Path):
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
            "session_id": str(uuid.uuid4()),
            "status": "executing",
            "mode": "execution",
            "name": "subagent-swe",
            "current_task": None,
            "recent_events": [],
        }
        engine._agent_comm = AsyncMock()
        engine._agent_comm.query_agent = AsyncMock(return_value=mock_result)

        db_mock = AsyncMock()
        session_id = uuid.uuid4()
        target_id = str(uuid.uuid4())

        result = await engine._execute_tool(
            "query_agent",
            {"session_id": target_id, "limit": 5},
            session_id=session_id,
            db=db_mock,
        )

        engine._agent_comm.query_agent.assert_called_once_with(
            db_mock,
            target_session_id=uuid.UUID(target_id),
            querying_session_id=session_id,
            limit=5,
        )
        parsed = json.loads(result["content"])
        assert parsed["status"] == "executing"
        assert not result.get("is_error", False)

    async def test_dispatch_send_to_agent(self, tmp_path: Path):
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
            "event_id": str(uuid.uuid4()),
            "target_session_id": str(uuid.uuid4()),
            "message": "Hello agent",
            "timestamp": "2026-03-16T00:00:00+00:00",
        }
        engine._agent_comm = AsyncMock()
        engine._agent_comm.send_to_agent = AsyncMock(return_value=mock_result)

        db_mock = AsyncMock()
        session_id = uuid.uuid4()
        target_id = str(uuid.uuid4())

        result = await engine._execute_tool(
            "send_to_agent",
            {"session_id": target_id, "message": "Hello agent"},
            session_id=session_id,
            db=db_mock,
        )

        engine._agent_comm.send_to_agent.assert_called_once_with(
            db_mock,
            sender_session_id=session_id,
            target_session_id=uuid.UUID(target_id),
            message="Hello agent",
        )
        parsed = json.loads(result["content"])
        assert parsed["message"] == "Hello agent"
        assert not result.get("is_error", False)


# ---------------------------------------------------------------------------
# Integration: API endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAgentMessageEndpoint:
    async def test_send_agent_message_200(
        self,
        client: AsyncClient,
        parent_session: SessionModel,
        child_session_a: SessionModel,
    ):
        resp = await client.post(
            f"/api/sessions/{parent_session.id}/messages/agent",
            json={
                "target_session_id": str(child_session_a.id),
                "message": "Status update please",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_session_id"] == str(child_session_a.id)
        assert data["message"] == "Status update please"

    async def test_send_agent_message_sender_not_found_404(
        self,
        client: AsyncClient,
    ):
        fake_id = uuid.uuid4()
        resp = await client.post(
            f"/api/sessions/{fake_id}/messages/agent",
            json={
                "target_session_id": str(uuid.uuid4()),
                "message": "Hello",
            },
        )
        assert resp.status_code == 404

    async def test_send_agent_message_target_not_found_404(
        self,
        client: AsyncClient,
        parent_session: SessionModel,
    ):
        resp = await client.post(
            f"/api/sessions/{parent_session.id}/messages/agent",
            json={
                "target_session_id": str(uuid.uuid4()),
                "message": "Hello",
            },
        )
        assert resp.status_code == 404
