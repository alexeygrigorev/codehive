"""Tests for read_issue and write_issue_log tools: schema, orchestrator, dispatch, round-trip."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.db.models import Base, Issue, IssueLogEntry, Project
from codehive.db.models import Session as SessionModel
from codehive.engine.orchestrator import ORCHESTRATOR_ALLOWED_TOOLS, filter_tools
from codehive.engine.tools.read_issue import READ_ISSUE_TOOL
from codehive.engine.tools.write_issue_log import WRITE_ISSUE_LOG_TOOL
from codehive.engine.zai_engine import TOOL_DEFINITIONS

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
async def session_row(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name=f"agent-session-{project.id}",
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
async def issue(db_session: AsyncSession, project: Project) -> Issue:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    iss = Issue(
        project_id=project.id,
        title="Test Issue",
        description="A test issue description",
        acceptance_criteria="- [ ] Criterion 1\n- [ ] Criterion 2",
        status="open",
        priority=1,
        assigned_agent="swe",
        created_at=now,
        updated_at=now,
    )
    db_session.add(iss)
    await db_session.commit()
    await db_session.refresh(iss)
    return iss


def _make_engine():
    """Build a ZaiEngine with mocked dependencies."""
    from codehive.engine.zai_engine import ZaiEngine

    engine = ZaiEngine(
        client=AsyncMock(),
        event_bus=MagicMock(),
        file_ops=MagicMock(),
        shell_runner=MagicMock(),
        git_ops=MagicMock(),
        diff_service=MagicMock(),
        model="test",
    )
    engine._event_bus = None
    return engine


# ---------------------------------------------------------------------------
# Unit: Tool schema validation
# ---------------------------------------------------------------------------


class TestReadIssueToolSchema:
    def test_name(self):
        assert READ_ISSUE_TOOL["name"] == "read_issue"

    def test_issue_id_required(self):
        schema = READ_ISSUE_TOOL["input_schema"]
        assert "issue_id" in schema["required"]

    def test_issue_id_is_string(self):
        props = READ_ISSUE_TOOL["input_schema"]["properties"]
        assert props["issue_id"]["type"] == "string"

    def test_input_schema_structure(self):
        schema = READ_ISSUE_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema


class TestWriteIssueLogToolSchema:
    def test_name(self):
        assert WRITE_ISSUE_LOG_TOOL["name"] == "write_issue_log"

    def test_required_fields(self):
        schema = WRITE_ISSUE_LOG_TOOL["input_schema"]
        assert "issue_id" in schema["required"]
        assert "agent_role" in schema["required"]
        assert "content" in schema["required"]

    def test_all_fields_are_strings(self):
        props = WRITE_ISSUE_LOG_TOOL["input_schema"]["properties"]
        for field in ("issue_id", "agent_role", "content"):
            assert props[field]["type"] == "string"

    def test_input_schema_structure(self):
        schema = WRITE_ISSUE_LOG_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema


# ---------------------------------------------------------------------------
# Unit: Tools registered in TOOL_DEFINITIONS
# ---------------------------------------------------------------------------


class TestToolRegistration:
    def test_read_issue_in_tool_definitions(self):
        names = {t["name"] for t in TOOL_DEFINITIONS}
        assert "read_issue" in names

    def test_write_issue_log_in_tool_definitions(self):
        names = {t["name"] for t in TOOL_DEFINITIONS}
        assert "write_issue_log" in names


# ---------------------------------------------------------------------------
# Unit: Orchestrator allowed tools
# ---------------------------------------------------------------------------


class TestOrchestratorAllowedTools:
    def test_read_issue_in_allowed_tools(self):
        assert "read_issue" in ORCHESTRATOR_ALLOWED_TOOLS

    def test_write_issue_log_in_allowed_tools(self):
        assert "write_issue_log" in ORCHESTRATOR_ALLOWED_TOOLS

    def test_filter_tools_includes_both(self):
        tool_defs = [
            {"name": "read_file"},
            {"name": "edit_file"},
            {"name": "read_issue"},
            {"name": "write_issue_log"},
            {"name": "spawn_subagent"},
        ]
        filtered = filter_tools(tool_defs)
        names = {t["name"] for t in filtered}
        assert "read_issue" in names
        assert "write_issue_log" in names
        assert "edit_file" not in names


# ---------------------------------------------------------------------------
# Unit: Tool dispatch via _execute_tool_direct
# ---------------------------------------------------------------------------


class TestReadIssueDispatch:
    @pytest.mark.asyncio
    async def test_read_issue_valid(
        self, db_session: AsyncSession, session_row: SessionModel, issue: Issue
    ):
        engine = _make_engine()
        result = await engine._execute_tool_direct(
            "read_issue",
            {"issue_id": str(issue.id)},
            session_id=session_row.id,
            db=db_session,
        )

        assert "is_error" not in result or result.get("is_error") is not True
        data = json.loads(result["content"])
        assert data["id"] == str(issue.id)
        assert data["title"] == "Test Issue"
        assert data["description"] == "A test issue description"
        assert data["acceptance_criteria"] == "- [ ] Criterion 1\n- [ ] Criterion 2"
        assert data["status"] == "open"
        assert data["priority"] == 1
        assert data["assigned_agent"] == "swe"
        assert "created_at" in data
        assert "updated_at" in data
        assert "log_entries" in data
        assert isinstance(data["log_entries"], list)

    @pytest.mark.asyncio
    async def test_read_issue_not_found(self, db_session: AsyncSession, session_row: SessionModel):
        fake_id = str(uuid.uuid4())
        engine = _make_engine()
        result = await engine._execute_tool_direct(
            "read_issue",
            {"issue_id": fake_id},
            session_id=session_row.id,
            db=db_session,
        )

        assert result["is_error"] is True
        assert fake_id in result["content"]
        assert "not found" in result["content"]

    @pytest.mark.asyncio
    async def test_read_issue_no_session(self):
        engine = _make_engine()
        result = await engine._execute_tool_direct(
            "read_issue",
            {"issue_id": str(uuid.uuid4())},
            session_id=None,
            db=None,
        )

        assert result["is_error"] is True
        assert "requires an active session" in result["content"]

    @pytest.mark.asyncio
    async def test_read_issue_includes_log_entries(
        self, db_session: AsyncSession, session_row: SessionModel, issue: Issue
    ):
        # Add a log entry to the issue
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        entry = IssueLogEntry(
            issue_id=issue.id,
            agent_role="swe",
            content="Implementation complete",
            created_at=now,
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        engine = _make_engine()
        result = await engine._execute_tool_direct(
            "read_issue",
            {"issue_id": str(issue.id)},
            session_id=session_row.id,
            db=db_session,
        )

        data = json.loads(result["content"])
        assert len(data["log_entries"]) == 1
        log = data["log_entries"][0]
        assert log["id"] == str(entry.id)
        assert log["agent_role"] == "swe"
        assert log["content"] == "Implementation complete"
        assert "created_at" in log


class TestWriteIssueLogDispatch:
    @pytest.mark.asyncio
    async def test_write_issue_log_valid(
        self, db_session: AsyncSession, session_row: SessionModel, issue: Issue
    ):
        engine = _make_engine()
        result = await engine._execute_tool_direct(
            "write_issue_log",
            {
                "issue_id": str(issue.id),
                "agent_role": "qa",
                "content": "All tests pass",
            },
            session_id=session_row.id,
            db=db_session,
        )

        assert "is_error" not in result or result.get("is_error") is not True
        data = json.loads(result["content"])
        assert "id" in data
        assert data["issue_id"] == str(issue.id)
        assert data["agent_role"] == "qa"
        assert data["content"] == "All tests pass"
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_write_issue_log_not_found(
        self, db_session: AsyncSession, session_row: SessionModel
    ):
        fake_id = str(uuid.uuid4())
        engine = _make_engine()
        result = await engine._execute_tool_direct(
            "write_issue_log",
            {
                "issue_id": fake_id,
                "agent_role": "swe",
                "content": "Some content",
            },
            session_id=session_row.id,
            db=db_session,
        )

        assert result["is_error"] is True
        assert fake_id in result["content"]
        assert "not found" in result["content"]

    @pytest.mark.asyncio
    async def test_write_issue_log_no_session(self):
        engine = _make_engine()
        result = await engine._execute_tool_direct(
            "write_issue_log",
            {
                "issue_id": str(uuid.uuid4()),
                "agent_role": "swe",
                "content": "Some content",
            },
            session_id=None,
            db=None,
        )

        assert result["is_error"] is True
        assert "requires an active session" in result["content"]


# ---------------------------------------------------------------------------
# Integration: Round-trip read after write
# ---------------------------------------------------------------------------


class TestRoundTrip:
    @pytest.mark.asyncio
    async def test_write_then_read(
        self, db_session: AsyncSession, session_row: SessionModel, issue: Issue
    ):
        engine = _make_engine()

        # Write a log entry
        write_result = await engine._execute_tool_direct(
            "write_issue_log",
            {
                "issue_id": str(issue.id),
                "agent_role": "qa",
                "content": "Tests passed: 10/10",
            },
            session_id=session_row.id,
            db=db_session,
        )
        write_data = json.loads(write_result["content"])

        # Read the issue
        read_result = await engine._execute_tool_direct(
            "read_issue",
            {"issue_id": str(issue.id)},
            session_id=session_row.id,
            db=db_session,
        )
        read_data = json.loads(read_result["content"])

        # The log entry should appear in log_entries
        assert len(read_data["log_entries"]) == 1
        log = read_data["log_entries"][0]
        assert log["id"] == write_data["id"]
        assert log["agent_role"] == "qa"
        assert log["content"] == "Tests passed: 10/10"

    @pytest.mark.asyncio
    async def test_multiple_logs_different_roles(
        self, db_session: AsyncSession, session_row: SessionModel, issue: Issue
    ):
        engine = _make_engine()

        # Write multiple log entries with different roles
        for role, content in [
            ("swe", "Implementation done"),
            ("qa", "Tests passed"),
            ("pm", "ACCEPT"),
        ]:
            await engine._execute_tool_direct(
                "write_issue_log",
                {
                    "issue_id": str(issue.id),
                    "agent_role": role,
                    "content": content,
                },
                session_id=session_row.id,
                db=db_session,
            )

        # Read the issue
        read_result = await engine._execute_tool_direct(
            "read_issue",
            {"issue_id": str(issue.id)},
            session_id=session_row.id,
            db=db_session,
        )
        read_data = json.loads(read_result["content"])

        # All three entries should be present
        entries = read_data["log_entries"]
        assert len(entries) == 3
        roles = [e["agent_role"] for e in entries]
        assert "swe" in roles
        assert "qa" in roles
        assert "pm" in roles
