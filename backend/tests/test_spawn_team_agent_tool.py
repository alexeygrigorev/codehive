"""Tests for the spawn_team_agent tool: schema, handler, orchestrator integration."""

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

from codehive.db.models import AgentProfile, Base, Project, Task
from codehive.db.models import Session as SessionModel
from codehive.engine.orchestrator import ORCHESTRATOR_ALLOWED_TOOLS, filter_tools
from codehive.engine.tools.spawn_team_agent import (
    ROLE_DEFAULT_STEP,
    SPAWN_TEAM_AGENT_TOOL,
)
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
        engine="native",
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
async def swe_profile(db_session: AsyncSession, project: Project) -> AgentProfile:
    profile = AgentProfile(
        project_id=project.id,
        name="Alice",
        role="swe",
        avatar_seed="alice-seed",
        personality="Thorough and methodical",
        system_prompt_modifier="Always write tests first",
        preferred_engine="claude_code",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


@pytest_asyncio.fixture
async def qa_profile(db_session: AsyncSession, project: Project) -> AgentProfile:
    profile = AgentProfile(
        project_id=project.id,
        name="Bob",
        role="qa",
        avatar_seed="bob-seed",
        personality=None,
        system_prompt_modifier=None,
        preferred_engine=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


@pytest_asyncio.fixture
async def task(db_session: AsyncSession, orch_session: SessionModel) -> Task:
    t = Task(
        session_id=orch_session.id,
        title="Fix sidebar bug",
        instructions="The sidebar does not refresh after creation",
        status="pending",
        pipeline_status="backlog",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


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
    return engine


# ---------------------------------------------------------------------------
# Unit: Tool schema
# ---------------------------------------------------------------------------


class TestSpawnTeamAgentToolSchema:
    def test_name(self):
        assert SPAWN_TEAM_AGENT_TOOL["name"] == "spawn_team_agent"

    def test_required_params(self):
        schema = SPAWN_TEAM_AGENT_TOOL["input_schema"]
        assert "agent_profile_id" in schema["required"]
        assert "task_id" in schema["required"]
        assert "instructions" in schema["required"]

    def test_optional_pipeline_step(self):
        props = SPAWN_TEAM_AGENT_TOOL["input_schema"]["properties"]
        assert "pipeline_step" in props
        assert "pipeline_step" not in SPAWN_TEAM_AGENT_TOOL["input_schema"]["required"]


# ---------------------------------------------------------------------------
# Unit: Role-to-step mapping
# ---------------------------------------------------------------------------


class TestRoleDefaultStep:
    def test_swe_maps_to_implementing(self):
        assert ROLE_DEFAULT_STEP["swe"] == "implementing"

    def test_qa_maps_to_testing(self):
        assert ROLE_DEFAULT_STEP["qa"] == "testing"

    def test_pm_maps_to_grooming(self):
        assert ROLE_DEFAULT_STEP["pm"] == "grooming"

    def test_explicit_pipeline_step_overrides_default(self):
        """The handler should use explicit pipeline_step over role default."""
        # This is tested via the integration test below; here we just verify
        # the mapping exists and would produce a different value for pm.
        assert ROLE_DEFAULT_STEP["pm"] == "grooming"
        # "accepting" is a valid override for pm


# ---------------------------------------------------------------------------
# Integration: Tool handler creates correct session
# ---------------------------------------------------------------------------


class TestSpawnTeamAgentHandler:
    @pytest.mark.asyncio
    async def test_creates_child_session(
        self,
        db_session: AsyncSession,
        orch_session: SessionModel,
        swe_profile: AgentProfile,
        task: Task,
    ):
        engine = _make_engine()

        result = await engine._execute_tool_direct(
            "spawn_team_agent",
            {
                "agent_profile_id": str(swe_profile.id),
                "task_id": str(task.id),
                "instructions": "Implement the sidebar fix",
            },
            session_id=orch_session.id,
            db=db_session,
        )

        assert "is_error" not in result or result.get("is_error") is not True
        data = json.loads(result["content"])
        assert "session_id" in data
        assert data["agent_name"] == "Alice"
        assert data["role"] == "swe"
        assert data["engine"] == "claude_code"

        # Verify child session in DB
        child = await db_session.get(SessionModel, uuid.UUID(data["session_id"]))
        assert child is not None
        assert child.parent_session_id == orch_session.id
        assert child.engine == "claude_code"
        assert child.role == "swe"
        assert child.task_id == task.id
        assert child.pipeline_step == "implementing"
        assert child.agent_profile_id == swe_profile.id
        assert child.project_id == orch_session.project_id

    @pytest.mark.asyncio
    async def test_stores_personality_in_config(
        self,
        db_session: AsyncSession,
        orch_session: SessionModel,
        swe_profile: AgentProfile,
        task: Task,
    ):
        engine = _make_engine()

        result = await engine._execute_tool_direct(
            "spawn_team_agent",
            {
                "agent_profile_id": str(swe_profile.id),
                "task_id": str(task.id),
                "instructions": "Implement the fix",
            },
            session_id=orch_session.id,
            db=db_session,
        )

        data = json.loads(result["content"])
        child = await db_session.get(SessionModel, uuid.UUID(data["session_id"]))
        assert child.config["personality"] == "Thorough and methodical"
        assert child.config["system_prompt_modifier"] == "Always write tests first"
        assert child.config["instructions"] == "Implement the fix"

    @pytest.mark.asyncio
    async def test_fallback_engine_when_preferred_is_none(
        self,
        db_session: AsyncSession,
        orch_session: SessionModel,
        qa_profile: AgentProfile,
        task: Task,
    ):
        """When agent profile has no preferred_engine, use parent session engine."""
        engine = _make_engine()

        result = await engine._execute_tool_direct(
            "spawn_team_agent",
            {
                "agent_profile_id": str(qa_profile.id),
                "task_id": str(task.id),
                "instructions": "Test the implementation",
            },
            session_id=orch_session.id,
            db=db_session,
        )

        data = json.loads(result["content"])
        assert data["engine"] == "native"  # parent session engine
        assert data["role"] == "qa"

        child = await db_session.get(SessionModel, uuid.UUID(data["session_id"]))
        assert child.engine == "native"
        assert child.pipeline_step == "testing"
        # No personality/system_prompt_modifier since qa_profile has None
        assert "personality" not in child.config
        assert "system_prompt_modifier" not in child.config

    @pytest.mark.asyncio
    async def test_explicit_pipeline_step_override(
        self,
        db_session: AsyncSession,
        orch_session: SessionModel,
        swe_profile: AgentProfile,
        task: Task,
    ):
        """Explicit pipeline_step overrides role default."""
        # Temporarily change swe_profile role to pm for this test
        pm_profile = AgentProfile(
            project_id=orch_session.project_id,
            name="Carol",
            role="pm",
            avatar_seed="carol-seed",
            preferred_engine="native",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(pm_profile)
        await db_session.commit()
        await db_session.refresh(pm_profile)

        engine = _make_engine()

        result = await engine._execute_tool_direct(
            "spawn_team_agent",
            {
                "agent_profile_id": str(pm_profile.id),
                "task_id": str(task.id),
                "instructions": "Accept the task",
                "pipeline_step": "accepting",
            },
            session_id=orch_session.id,
            db=db_session,
        )

        data = json.loads(result["content"])
        child = await db_session.get(SessionModel, uuid.UUID(data["session_id"]))
        assert child.pipeline_step == "accepting"  # overridden, not "grooming"

    @pytest.mark.asyncio
    async def test_error_agent_profile_not_found(
        self,
        db_session: AsyncSession,
        orch_session: SessionModel,
        task: Task,
    ):
        engine = _make_engine()

        result = await engine._execute_tool_direct(
            "spawn_team_agent",
            {
                "agent_profile_id": str(uuid.uuid4()),
                "task_id": str(task.id),
                "instructions": "Do something",
            },
            session_id=orch_session.id,
            db=db_session,
        )

        assert result["is_error"] is True
        assert "Agent profile not found" in result["content"]

    @pytest.mark.asyncio
    async def test_error_task_not_found(
        self,
        db_session: AsyncSession,
        orch_session: SessionModel,
        swe_profile: AgentProfile,
    ):
        engine = _make_engine()

        result = await engine._execute_tool_direct(
            "spawn_team_agent",
            {
                "agent_profile_id": str(swe_profile.id),
                "task_id": str(uuid.uuid4()),
                "instructions": "Do something",
            },
            session_id=orch_session.id,
            db=db_session,
        )

        assert result["is_error"] is True
        assert "Task not found" in result["content"]

    @pytest.mark.asyncio
    async def test_error_no_session(self):
        engine = _make_engine()

        result = await engine._execute_tool_direct(
            "spawn_team_agent",
            {
                "agent_profile_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "instructions": "Do something",
            },
            session_id=None,
            db=None,
        )

        assert result["is_error"] is True
        assert "requires an active session" in result["content"]


# ---------------------------------------------------------------------------
# Integration: Orchestrator allowed tools
# ---------------------------------------------------------------------------


class TestOrchestratorIntegration:
    def test_spawn_team_agent_in_allowed_tools(self):
        assert "spawn_team_agent" in ORCHESTRATOR_ALLOWED_TOOLS

    def test_spawn_team_agent_in_tool_definitions(self):
        names = {t["name"] for t in TOOL_DEFINITIONS}
        assert "spawn_team_agent" in names

    def test_filter_tools_includes_spawn_team_agent(self):
        tool_defs = [
            {"name": "read_file"},
            {"name": "edit_file"},
            {"name": "spawn_team_agent"},
        ]
        filtered = filter_tools(tool_defs)
        names = {t["name"] for t in filtered}
        assert "spawn_team_agent" in names
        assert "edit_file" not in names
