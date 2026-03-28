"""Tests for spawn config: prompt templates, engine config, orchestrator integration."""

from __future__ import annotations

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
from codehive.core.orchestrator_service import (
    OrchestratorService,
    build_instructions,
    clear_registry,
)
from codehive.core.roles import BUILTIN_ROLES
from codehive.core.session import create_session as create_db_session
from codehive.core.spawn_config import (
    delete_prompt_template,
    get_engine_config,
    get_engine_extra_args,
    get_prompt_templates,
    get_system_prompt_for_role,
    set_engine_config,
    set_prompt_template,
)
from codehive.core.task_queue import create_task
from codehive.db.models import Base, Project
from codehive.db.models import Session as SessionModel

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

    # In-memory SQLite: just dispose, no need to drop tables
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


@pytest_asyncio.fixture(autouse=True)
async def cleanup_registry():
    clear_registry()
    yield
    clear_registry()


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
            json={"email": "spawn@test.com", "username": "spawnuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit: prompt templates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPromptTemplates:
    async def test_get_default_templates(self, project: Project):
        """All four roles should return default prompts."""
        templates = get_prompt_templates(project)
        assert len(templates) == len(BUILTIN_ROLES)
        for t in templates:
            assert t["is_custom"] is False
            assert t["system_prompt"] == BUILTIN_ROLES[t["role"]]["system_prompt"]

    async def test_set_custom_template(self, db_session: AsyncSession, project: Project):
        """Setting a custom prompt should override the default."""
        result = await set_prompt_template(db_session, project.id, "swe", "Custom SWE prompt")
        assert result["is_custom"] is True
        assert result["system_prompt"] == "Custom SWE prompt"
        assert result["role"] == "swe"

        # Verify via get_prompt_templates
        templates = get_prompt_templates(project)
        swe = next(t for t in templates if t["role"] == "swe")
        assert swe["is_custom"] is True
        assert swe["system_prompt"] == "Custom SWE prompt"

        # Others remain default
        pm = next(t for t in templates if t["role"] == "pm")
        assert pm["is_custom"] is False

    async def test_delete_custom_template(self, db_session: AsyncSession, project: Project):
        """Deleting a custom prompt reverts to default."""
        await set_prompt_template(db_session, project.id, "swe", "Custom")
        result = await delete_prompt_template(db_session, project.id, "swe")
        assert result["is_custom"] is False
        assert result["system_prompt"] == BUILTIN_ROLES["swe"]["system_prompt"]

    async def test_get_system_prompt_default(self, project: Project):
        prompt = get_system_prompt_for_role(project, "swe")
        assert prompt == BUILTIN_ROLES["swe"]["system_prompt"]

    async def test_get_system_prompt_custom(self, db_session: AsyncSession, project: Project):
        await set_prompt_template(db_session, project.id, "qa", "Custom QA")
        prompt = get_system_prompt_for_role(project, "qa")
        assert prompt == "Custom QA"


# ---------------------------------------------------------------------------
# Unit: engine config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEngineConfig:
    async def test_empty_engine_config(self, project: Project):
        configs = get_engine_config(project)
        assert configs == []

    async def test_set_engine_config(self, db_session: AsyncSession, project: Project):
        result = await set_engine_config(db_session, project.id, "claude_code", ["--verbose"])
        assert result["engine"] == "claude_code"
        assert result["extra_args"] == ["--verbose"]

    async def test_get_engine_config_multiple(self, db_session: AsyncSession, project: Project):
        await set_engine_config(db_session, project.id, "claude_code", ["--verbose"])
        await set_engine_config(db_session, project.id, "codex", ["--full-auto"])

        # Refresh the project to get latest knowledge from DB
        await db_session.refresh(project)
        configs = get_engine_config(project)
        assert len(configs) == 2
        engines = {c["engine"] for c in configs}
        assert engines == {"claude_code", "codex"}

    async def test_get_engine_extra_args(self, db_session: AsyncSession, project: Project):
        await set_engine_config(db_session, project.id, "claude_code", ["--verbose", "--fast"])
        args = get_engine_extra_args(project, "claude_code")
        assert args == ["--verbose", "--fast"]

    async def test_get_engine_extra_args_missing(self, project: Project):
        args = get_engine_extra_args(project, "nonexistent")
        assert args == []


# ---------------------------------------------------------------------------
# Unit: spawn config storage in session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSpawnConfigStorage:
    async def test_spawn_config_round_trips(self, db_session: AsyncSession, project: Project):
        """spawn_config stored in session.config survives DB round-trip."""
        spawn_config = {
            "system_prompt": "You are a Software Engineer.",
            "initial_message": "Implement the feature.",
            "engine": "claude_code",
            "engine_args": ["--verbose"],
            "role": "swe",
            "pipeline_step": "implementing",
        }
        session = await create_db_session(
            db_session,
            project_id=project.id,
            name="test-session",
            engine="claude_code",
            mode="execution",
        )
        session.config = {"spawn_config": spawn_config}
        await db_session.commit()
        await db_session.refresh(session)

        assert session.config["spawn_config"] == spawn_config
        assert session.config["spawn_config"]["system_prompt"] == "You are a Software Engineer."
        assert session.config["spawn_config"]["engine_args"] == ["--verbose"]


# ---------------------------------------------------------------------------
# Unit: orchestrator reads custom templates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrchestratorSpawnConfig:
    async def test_default_spawn_stores_config(
        self, db_session_factory, db_session: AsyncSession, project: Project
    ):
        """_default_spawn_and_run stores spawn_config in child session."""
        # Create orchestrator session
        orch_session = SessionModel(
            project_id=project.id,
            name=f"orchestrator-{project.id}",
            engine="claude_code",
            mode="orchestrator",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(orch_session)
        await db_session.commit()
        await db_session.refresh(orch_session)

        # Create a task
        task = await create_task(db_session, session_id=orch_session.id, title="Test task")

        service = OrchestratorService(
            db_session_factory=db_session_factory,
            project_id=project.id,
        )

        await service._default_spawn_and_run(
            task_id=task.id,
            step="implementing",
            role="swe",
            mode="execution",
            instructions="Implement feature X",
        )

        # Find the child session
        from sqlalchemy import select

        async with db_session_factory() as db:
            result = await db.execute(
                select(SessionModel).where(
                    SessionModel.task_id == task.id,
                    SessionModel.pipeline_step == "implementing",
                )
            )
            child = result.scalar_one()
            assert "spawn_config" in child.config
            sc = child.config["spawn_config"]
            assert sc["role"] == "swe"
            assert sc["pipeline_step"] == "implementing"
            assert sc["engine"] == "claude_code"
            assert sc["initial_message"] == "Implement feature X"
            # Default system prompt from BUILTIN_ROLES
            assert sc["system_prompt"] == BUILTIN_ROLES["swe"]["system_prompt"]

    async def test_custom_prompt_used_in_spawn(
        self, db_session_factory, db_session: AsyncSession, project: Project
    ):
        """Custom prompt template is used when spawning."""
        # Set custom SWE prompt
        await set_prompt_template(db_session, project.id, "swe", "Custom SWE agent prompt")

        # Create orchestrator session
        orch_session = SessionModel(
            project_id=project.id,
            name=f"orchestrator-{project.id}",
            engine="claude_code",
            mode="orchestrator",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(orch_session)
        await db_session.commit()
        await db_session.refresh(orch_session)

        task = await create_task(db_session, session_id=orch_session.id, title="Test task")

        service = OrchestratorService(
            db_session_factory=db_session_factory,
            project_id=project.id,
        )

        await service._default_spawn_and_run(
            task_id=task.id,
            step="implementing",
            role="swe",
            mode="execution",
            instructions="Implement feature Y",
        )

        from sqlalchemy import select

        async with db_session_factory() as db:
            result = await db.execute(
                select(SessionModel).where(
                    SessionModel.task_id == task.id,
                    SessionModel.pipeline_step == "implementing",
                )
            )
            child = result.scalar_one()
            assert child.config["spawn_config"]["system_prompt"] == "Custom SWE agent prompt"


# ---------------------------------------------------------------------------
# Integration: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPromptTemplateAPI:
    async def test_get_prompt_templates(self, client: AsyncClient, project: Project):
        resp = await client.get(f"/api/projects/{project.id}/prompt-templates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == len(BUILTIN_ROLES)
        roles = {t["role"] for t in data}
        assert roles == set(BUILTIN_ROLES.keys())

    async def test_put_prompt_template(self, client: AsyncClient, project: Project):
        resp = await client.put(
            f"/api/projects/{project.id}/prompt-templates/swe",
            json={"system_prompt": "custom swe prompt"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "swe"
        assert data["system_prompt"] == "custom swe prompt"
        assert data["is_custom"] is True

        # Verify via GET
        resp2 = await client.get(f"/api/projects/{project.id}/prompt-templates")
        templates = resp2.json()
        swe = next(t for t in templates if t["role"] == "swe")
        assert swe["system_prompt"] == "custom swe prompt"
        assert swe["is_custom"] is True

    async def test_delete_prompt_template(self, client: AsyncClient, project: Project):
        # Set then delete
        await client.put(
            f"/api/projects/{project.id}/prompt-templates/swe",
            json={"system_prompt": "custom"},
        )
        resp = await client.delete(f"/api/projects/{project.id}/prompt-templates/swe")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_custom"] is False
        assert data["system_prompt"] == BUILTIN_ROLES["swe"]["system_prompt"]

    async def test_put_invalid_role_returns_422(self, client: AsyncClient, project: Project):
        resp = await client.put(
            f"/api/projects/{project.id}/prompt-templates/invalid_role",
            json={"system_prompt": "x"},
        )
        assert resp.status_code == 422

    async def test_get_templates_not_found(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/projects/{fake_id}/prompt-templates")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestEngineConfigAPI:
    async def test_get_engine_config_empty(self, client: AsyncClient, project: Project):
        resp = await client.get(f"/api/projects/{project.id}/engine-config")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_put_engine_config(self, client: AsyncClient, project: Project):
        resp = await client.put(
            f"/api/projects/{project.id}/engine-config/claude_code",
            json={"extra_args": ["--verbose"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["engine"] == "claude_code"
        assert data["extra_args"] == ["--verbose"]

    async def test_put_multiple_engines(self, client: AsyncClient, project: Project):
        await client.put(
            f"/api/projects/{project.id}/engine-config/claude_code",
            json={"extra_args": ["--verbose"]},
        )
        await client.put(
            f"/api/projects/{project.id}/engine-config/codex",
            json={"extra_args": ["--full-auto"]},
        )
        resp = await client.get(f"/api/projects/{project.id}/engine-config")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_engine_config_not_found(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/projects/{fake_id}/engine-config")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Unit: build_instructions output format
# ---------------------------------------------------------------------------


class TestBuildInstructions:
    def test_grooming_instructions(self):
        result = build_instructions(
            step="grooming",
            task_title="Add feature X",
            task_instructions="Build a new form",
        )
        assert "Task to Groom" in result
        assert "Add feature X" in result
        assert "Build a new form" in result

    def test_implementing_instructions(self):
        result = build_instructions(
            step="implementing",
            task_title="Add feature X",
            task_instructions="Build a new form",
            acceptance_criteria="- Must have validation",
        )
        assert "Task to Implement" in result
        assert "Must have validation" in result

    def test_testing_instructions(self):
        result = build_instructions(
            step="testing",
            task_title="Add feature X",
            task_instructions=None,
            acceptance_criteria="- Tests pass",
            agent_output="Implementation done",
        )
        assert "Task to Test" in result
        assert "VERDICT: PASS" in result

    def test_accepting_instructions(self):
        result = build_instructions(
            step="accepting",
            task_title="Add feature X",
            task_instructions=None,
            agent_output="QA evidence",
        )
        assert "Task to Accept" in result
        assert "VERDICT: ACCEPT" in result
