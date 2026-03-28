"""Tests for Agent Profile (team) model, generation, CRUD API, and orchestrator integration."""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.issues import create_issue, create_issue_log_entry
from codehive.core.project import create_project
from codehive.core.team import (
    DICEBEAR_BASE_URL,
    NAME_POOL,
    avatar_url_for_seed,
)
from codehive.db.models import AgentProfile, Base, Project

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
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register a test user and get auth token
        resp = await ac.post(
            "/api/auth/register",
            json={"email": "test@test.com", "username": "testuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


async def _create_project(db: AsyncSession, name: str = "test-project") -> Project:
    return await create_project(db, name=name)


# ---------------------------------------------------------------------------
# Unit: AgentProfile model and team generation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTeamGeneration:
    async def test_default_team_created_on_project_create(self, db_session: AsyncSession):
        """Creating a project auto-generates 6 agent profiles."""
        project = await _create_project(db_session)
        result = await db_session.execute(
            select(AgentProfile).where(AgentProfile.project_id == project.id)
        )
        profiles = list(result.scalars().all())
        assert len(profiles) == 6

    async def test_team_role_distribution(self, db_session: AsyncSession):
        """Team has 1 PM, 2 SWE, 2 QA, 1 OnCall."""
        project = await _create_project(db_session)
        result = await db_session.execute(
            select(AgentProfile).where(AgentProfile.project_id == project.id)
        )
        profiles = list(result.scalars().all())
        roles = [p.role for p in profiles]
        assert roles.count("pm") == 1
        assert roles.count("swe") == 2
        assert roles.count("qa") == 2
        assert roles.count("oncall") == 1

    async def test_each_profile_has_name_and_avatar_seed(self, db_session: AsyncSession):
        """Every agent profile has a non-empty name and avatar_seed."""
        project = await _create_project(db_session)
        result = await db_session.execute(
            select(AgentProfile).where(AgentProfile.project_id == project.id)
        )
        profiles = list(result.scalars().all())
        for p in profiles:
            assert p.name, "Name must not be empty"
            assert p.avatar_seed, "Avatar seed must not be empty"
            assert p.name in NAME_POOL

    async def test_avatar_seed_deterministic(self, db_session: AsyncSession):
        """avatar_seed = name-project_id, which is deterministic."""
        project = await _create_project(db_session)
        result = await db_session.execute(
            select(AgentProfile).where(AgentProfile.project_id == project.id)
        )
        profiles = list(result.scalars().all())
        for p in profiles:
            assert p.avatar_seed == f"{p.name}-{project.id}"

    async def test_two_projects_get_independent_teams(self, db_session: AsyncSession):
        """Two different projects each get 6 profiles."""
        p1 = await _create_project(db_session, name="project-1")
        p2 = await _create_project(db_session, name="project-2")

        r1 = await db_session.execute(select(AgentProfile).where(AgentProfile.project_id == p1.id))
        r2 = await db_session.execute(select(AgentProfile).where(AgentProfile.project_id == p2.id))
        assert len(list(r1.scalars().all())) == 6
        assert len(list(r2.scalars().all())) == 6

    async def test_project_team_relationship(self, db_session: AsyncSession):
        """Project.team returns associated AgentProfiles."""
        project = await _create_project(db_session)
        await db_session.refresh(project, attribute_names=["team"])
        assert len(project.team) == 6

    async def test_avatar_url_helper(self):
        """avatar_url_for_seed constructs the correct DiceBear URL."""
        url = avatar_url_for_seed("test-seed")
        assert url == f"{DICEBEAR_BASE_URL}?seed=test-seed"


# ---------------------------------------------------------------------------
# Unit: Team CRUD operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTeamCRUD:
    async def test_add_agent_profile(self, db_session: AsyncSession):
        """Add a new agent profile to a project."""
        project = await _create_project(db_session)
        profile = AgentProfile(
            project_id=project.id,
            name="NewAgent",
            role="swe",
            avatar_seed=f"NewAgent-{project.id}",
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        assert profile.id is not None
        assert profile.name == "NewAgent"

    async def test_update_agent_profile_name(self, db_session: AsyncSession):
        """Update an agent profile's name."""
        project = await _create_project(db_session)
        result = await db_session.execute(
            select(AgentProfile).where(AgentProfile.project_id == project.id).limit(1)
        )
        profile = result.scalar_one()
        profile.name = "Renamed"
        await db_session.commit()
        await db_session.refresh(profile)
        assert profile.name == "Renamed"

    async def test_delete_agent_profile(self, db_session: AsyncSession):
        """Delete an agent profile."""
        project = await _create_project(db_session)
        result = await db_session.execute(
            select(AgentProfile).where(AgentProfile.project_id == project.id).limit(1)
        )
        profile = result.scalar_one()
        profile_id = profile.id
        await db_session.delete(profile)
        await db_session.commit()
        deleted = await db_session.get(AgentProfile, profile_id)
        assert deleted is None


# ---------------------------------------------------------------------------
# Unit: Issue log entry with agent_profile_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLogEntryWithProfile:
    async def test_create_log_entry_with_profile(self, db_session: AsyncSession):
        """Log entry can be created with an agent_profile_id."""
        project = await _create_project(db_session)
        issue = await create_issue(db_session, project_id=project.id, title="Test Issue")
        result = await db_session.execute(
            select(AgentProfile).where(AgentProfile.project_id == project.id).limit(1)
        )
        profile = result.scalar_one()

        entry = await create_issue_log_entry(
            db_session,
            issue_id=issue.id,
            agent_role="swe",
            content="Did some work",
            agent_profile_id=profile.id,
        )
        assert entry.agent_profile_id == profile.id

    async def test_create_log_entry_without_profile(self, db_session: AsyncSession):
        """Log entry works without agent_profile_id (backward compat)."""
        project = await _create_project(db_session)
        issue = await create_issue(db_session, project_id=project.id, title="Test Issue")
        entry = await create_issue_log_entry(
            db_session,
            issue_id=issue.id,
            agent_role="swe",
            content="Backward compat",
        )
        assert entry.agent_profile_id is None


# ---------------------------------------------------------------------------
# Integration: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTeamAPI:
    async def test_create_project_returns_team_via_get(self, client: AsyncClient):
        """POST /api/projects creates a project, GET /team returns 6 profiles."""
        resp = await client.post("/api/projects", json={"name": "api-project"})
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        resp = await client.get(f"/api/projects/{project_id}/team")
        assert resp.status_code == 200
        team = resp.json()
        assert len(team) == 6

        # Verify each profile has expected fields
        for member in team:
            assert "id" in member
            assert "name" in member
            assert "role" in member
            assert "avatar_seed" in member
            assert "avatar_url" in member
            assert member["avatar_url"].startswith(DICEBEAR_BASE_URL)

    async def test_add_team_member(self, client: AsyncClient):
        """POST /api/projects/{id}/team creates a new agent profile."""
        resp = await client.post("/api/projects", json={"name": "p1"})
        project_id = resp.json()["id"]

        resp = await client.post(
            f"/api/projects/{project_id}/team",
            json={"name": "NewAgent", "role": "swe"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "NewAgent"
        assert data["role"] == "swe"
        assert data["avatar_url"].startswith(DICEBEAR_BASE_URL)

    async def test_update_team_member(self, client: AsyncClient):
        """PATCH /api/projects/{id}/team/{agent_id} updates the profile."""
        resp = await client.post("/api/projects", json={"name": "p2"})
        project_id = resp.json()["id"]

        team_resp = await client.get(f"/api/projects/{project_id}/team")
        agent_id = team_resp.json()[0]["id"]

        resp = await client.patch(
            f"/api/projects/{project_id}/team/{agent_id}",
            json={"name": "Renamed"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    async def test_delete_team_member(self, client: AsyncClient):
        """DELETE /api/projects/{id}/team/{agent_id} removes the profile."""
        resp = await client.post("/api/projects", json={"name": "p3"})
        project_id = resp.json()["id"]

        team_resp = await client.get(f"/api/projects/{project_id}/team")
        agent_id = team_resp.json()[0]["id"]
        original_count = len(team_resp.json())

        resp = await client.delete(f"/api/projects/{project_id}/team/{agent_id}")
        assert resp.status_code == 204

        team_resp = await client.get(f"/api/projects/{project_id}/team")
        assert len(team_resp.json()) == original_count - 1

    async def test_add_to_nonexistent_project_404(self, client: AsyncClient):
        """POST /api/projects/{fake_id}/team returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            f"/api/projects/{fake_id}/team",
            json={"name": "Agent", "role": "swe"},
        )
        assert resp.status_code == 404

    async def test_generate_team_for_empty_project(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """POST /api/projects/{id}/team/generate on a project with no team returns 201 and 6 profiles."""
        # Create a project without auto-generating a team by inserting directly
        project = Project(name="legacy-no-team", knowledge={})
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        project_id = str(project.id)

        resp = await client.post(f"/api/projects/{project_id}/team/generate")
        assert resp.status_code == 201
        team = resp.json()
        assert len(team) == 6

        # Verify role distribution
        roles = [m["role"] for m in team]
        assert roles.count("pm") == 1
        assert roles.count("swe") == 2
        assert roles.count("qa") == 2
        assert roles.count("oncall") == 1

    async def test_generate_team_conflict_when_team_exists(self, client: AsyncClient):
        """POST /api/projects/{id}/team/generate on a project that already has a team returns 409."""
        # create_project auto-generates a team
        resp = await client.post("/api/projects", json={"name": "has-team"})
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        resp = await client.post(f"/api/projects/{project_id}/team/generate")
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    async def test_generate_team_nonexistent_project_404(self, client: AsyncClient):
        """POST /api/projects/{fake_id}/team/generate returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.post(f"/api/projects/{fake_id}/team/generate")
        assert resp.status_code == 404

    async def test_generate_then_get_returns_same_team(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """After calling generate, GET /api/projects/{id}/team returns the same 6 profiles."""
        project = Project(name="generate-then-get", knowledge={})
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        project_id = str(project.id)

        gen_resp = await client.post(f"/api/projects/{project_id}/team/generate")
        assert gen_resp.status_code == 201
        generated = gen_resp.json()

        get_resp = await client.get(f"/api/projects/{project_id}/team")
        assert get_resp.status_code == 200
        fetched = get_resp.json()
        assert len(fetched) == 6

        generated_ids = sorted([m["id"] for m in generated])
        fetched_ids = sorted([m["id"] for m in fetched])
        assert generated_ids == fetched_ids

    async def test_issue_logs_include_agent_info(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """GET /api/issues/{id}/logs returns agent_name and agent_avatar_url for entries with a profile."""
        # Create project + issue via API
        resp = await client.post("/api/projects", json={"name": "log-project"})
        project_id = resp.json()["id"]

        resp = await client.post(
            f"/api/projects/{project_id}/issues",
            json={"title": "Log test issue"},
        )
        issue_id = resp.json()["id"]

        # Get a team member
        team_resp = await client.get(f"/api/projects/{project_id}/team")
        agent = team_resp.json()[0]

        # Create a log entry with agent_profile_id via core function
        await create_issue_log_entry(
            db_session,
            issue_id=uuid.UUID(issue_id),
            agent_role=agent["role"],
            content="Work done by agent",
            agent_profile_id=uuid.UUID(agent["id"]),
        )

        # Fetch logs via API
        resp = await client.get(f"/api/issues/{issue_id}/logs")
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        log_with_profile = [lg for lg in logs if lg["agent_profile_id"] is not None]
        assert len(log_with_profile) == 1
        assert log_with_profile[0]["agent_name"] == agent["name"]
        assert log_with_profile[0]["agent_avatar_url"].startswith(DICEBEAR_BASE_URL)

    async def test_issue_logs_without_profile_have_null_agent(self, client: AsyncClient):
        """GET /api/issues/{id}/logs returns null agent fields for legacy entries."""
        resp = await client.post("/api/projects", json={"name": "legacy-project"})
        project_id = resp.json()["id"]

        resp = await client.post(
            f"/api/projects/{project_id}/issues",
            json={"title": "Legacy issue"},
        )
        issue_id = resp.json()["id"]

        # Create log entry without profile
        resp = await client.post(
            f"/api/issues/{issue_id}/logs",
            json={"agent_role": "swe", "content": "Old log entry"},
        )
        assert resp.status_code == 201

        # Fetch logs
        resp = await client.get(f"/api/issues/{issue_id}/logs")
        logs = resp.json()
        assert len(logs) >= 1
        assert logs[0]["agent_name"] is None
        assert logs[0]["agent_avatar_url"] is None

    async def test_session_endpoints_return_agent_fields(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """GET session endpoints return populated agent_name and agent_avatar_url."""
        from sqlalchemy import select as sa_select

        # Create project (auto-generates team)
        resp = await client.post("/api/projects", json={"name": "session-agent-project"})
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        # Get an SWE team member
        team_resp = await client.get(f"/api/projects/{project_id}/team")
        swe_agents = [a for a in team_resp.json() if a["role"] == "swe"]
        assert len(swe_agents) >= 1
        agent = swe_agents[0]

        # Create a session with agent_profile_id
        resp = await client.post(
            f"/api/projects/{project_id}/sessions",
            json={
                "name": "agent-session",
                "engine": "claude_code",
                "mode": "execution",
                "role": "swe",
            },
        )
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        # Manually set agent_profile_id on the session (simulating orchestrator)
        from codehive.db.models import Session as SessionModel

        result = await db_session.execute(
            sa_select(SessionModel).where(SessionModel.id == uuid.UUID(session_id))
        )
        sess_obj = result.scalar_one()
        sess_obj.agent_profile_id = uuid.UUID(agent["id"])
        await db_session.commit()

        # GET single session should have agent fields
        resp = await client.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_name"] == agent["name"]
        assert data["agent_avatar_url"] is not None
        assert data["agent_avatar_url"].startswith(DICEBEAR_BASE_URL)

        # GET list sessions should also have agent fields
        resp = await client.get(f"/api/projects/{project_id}/sessions")
        assert resp.status_code == 200
        sessions = resp.json()
        matched = [s for s in sessions if s["id"] == session_id]
        assert len(matched) == 1
        assert matched[0]["agent_name"] == agent["name"]
        assert matched[0]["agent_avatar_url"] is not None

    async def test_session_without_profile_has_null_agent_fields(self, client: AsyncClient):
        """Sessions without agent_profile_id return null agent fields."""
        resp = await client.post("/api/projects", json={"name": "no-agent-project"})
        project_id = resp.json()["id"]

        resp = await client.post(
            f"/api/projects/{project_id}/sessions",
            json={
                "name": "plain-session",
                "engine": "claude_code",
                "mode": "execution",
            },
        )
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        resp = await client.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_name"] is None
        assert data["agent_avatar_url"] is None


# ---------------------------------------------------------------------------
# Unit: AgentProfile preferred_engine / preferred_model fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEngineFields:
    async def test_create_profile_with_engine(self, db_session: AsyncSession):
        """AgentProfile with preferred_engine and preferred_model persists correctly."""
        project = await _create_project(db_session)
        profile = AgentProfile(
            project_id=project.id,
            name="EngineAgent",
            role="swe",
            avatar_seed=f"EngineAgent-{project.id}",
            preferred_engine="claude_code",
            preferred_model="claude-sonnet-4-6",
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        assert profile.preferred_engine == "claude_code"
        assert profile.preferred_model == "claude-sonnet-4-6"

    async def test_create_profile_without_engine_defaults_none(self, db_session: AsyncSession):
        """AgentProfile without engine fields defaults to None (backward compat)."""
        project = await _create_project(db_session)
        profile = AgentProfile(
            project_id=project.id,
            name="NoEngineAgent",
            role="qa",
            avatar_seed=f"NoEngineAgent-{project.id}",
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        assert profile.preferred_engine is None
        assert profile.preferred_model is None

    async def test_default_team_engine_fields_are_none(self, db_session: AsyncSession):
        """generate_default_team creates profiles with preferred_engine=None."""
        project = await _create_project(db_session)
        result = await db_session.execute(
            select(AgentProfile).where(AgentProfile.project_id == project.id)
        )
        profiles = list(result.scalars().all())
        assert len(profiles) == 6
        for p in profiles:
            assert p.preferred_engine is None
            assert p.preferred_model is None


# ---------------------------------------------------------------------------
# Unit: Orchestrator engine resolution with preferred_engine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOrchestratorEngineResolution:
    @pytest_asyncio.fixture
    async def db_engine(self):
        engine = create_async_engine(SQLITE_URL)

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        # Disable FK checks for clean teardown
        async with engine.begin() as conn:
            await conn.execute(sa_text("PRAGMA foreign_keys=OFF"))
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    @pytest_asyncio.fixture
    async def db_session_factory(self, db_engine):
        return async_sessionmaker(db_engine, expire_on_commit=False)

    @pytest_asyncio.fixture
    async def orch_db_session(self, db_session_factory) -> AsyncGenerator[AsyncSession, None]:
        async with db_session_factory() as session:
            yield session

    async def test_spawn_uses_preferred_engine(self, db_session_factory, orch_db_session):
        """When agent profile has preferred_engine, child session uses it."""
        from codehive.core.orchestrator_service import OrchestratorService
        from codehive.core.session import create_session as create_db_session
        from codehive.db.models import Session as SessionModel

        db = orch_db_session
        project = Project(name="orch-test", knowledge={})
        db.add(project)
        await db.flush()

        profile = AgentProfile(
            project_id=project.id,
            name="Alice",
            role="swe",
            avatar_seed=f"Alice-{project.id}",
            preferred_engine="codex",
            preferred_model="gpt-5.4",
        )
        db.add(profile)
        await db.flush()

        # Create orchestrator session
        orch_session = await create_db_session(
            db,
            project_id=project.id,
            name=f"orchestrator-{project.id}",
            engine="claude_code",
            mode="orchestrator",
        )
        # Create a task
        from codehive.core.task_queue import create_task

        task = await create_task(db, session_id=orch_session.id, title="Test task")
        await db.commit()

        @asynccontextmanager
        async def _factory():
            async with db_session_factory() as s:
                yield s

        orch = OrchestratorService(
            db_session_factory=_factory,
            project_id=project.id,
        )

        await orch._default_spawn_and_run(
            task_id=task.id,
            step="implementing",
            role="swe",
            mode="execution",
            instructions="do stuff",
            agent_profile_id=profile.id,
        )

        # Verify the child session was created with the preferred engine
        async with _factory() as s:
            result = await s.execute(
                select(SessionModel).where(
                    SessionModel.task_id == task.id,
                    SessionModel.pipeline_step == "implementing",
                )
            )
            child = result.scalar_one()
            assert child.engine == "codex"

    async def test_spawn_falls_back_when_no_preferred_engine(
        self, db_session_factory, orch_db_session
    ):
        """When agent profile has no preferred_engine, falls back to default."""
        from codehive.core.orchestrator_service import OrchestratorService
        from codehive.core.session import create_session as create_db_session
        from codehive.db.models import Session as SessionModel

        db = orch_db_session
        project = Project(name="orch-test-2", knowledge={})
        db.add(project)
        await db.flush()

        profile = AgentProfile(
            project_id=project.id,
            name="Bob",
            role="swe",
            avatar_seed=f"Bob-{project.id}",
            # No preferred_engine
        )
        db.add(profile)
        await db.flush()

        orch_session = await create_db_session(
            db,
            project_id=project.id,
            name=f"orchestrator-{project.id}",
            engine="claude_code",
            mode="orchestrator",
        )
        from codehive.core.task_queue import create_task

        task = await create_task(db, session_id=orch_session.id, title="Test task 2")
        await db.commit()

        @asynccontextmanager
        async def _factory():
            async with db_session_factory() as s:
                yield s

        orch = OrchestratorService(
            db_session_factory=_factory,
            project_id=project.id,
        )

        await orch._default_spawn_and_run(
            task_id=task.id,
            step="implementing",
            role="swe",
            mode="execution",
            instructions="do stuff",
            agent_profile_id=profile.id,
        )

        async with _factory() as s:
            result = await s.execute(
                select(SessionModel).where(
                    SessionModel.task_id == task.id,
                    SessionModel.pipeline_step == "implementing",
                )
            )
            child = result.scalar_one()
            # Should fall back to orchestrator's default engine
            assert child.engine == "claude_code"

    async def test_spawn_falls_back_when_no_profile(self, db_session_factory, orch_db_session):
        """When agent_profile_id is None, falls back to default engine."""
        from codehive.core.orchestrator_service import OrchestratorService
        from codehive.core.session import create_session as create_db_session
        from codehive.db.models import Session as SessionModel

        db = orch_db_session
        project = Project(name="orch-test-3", knowledge={})
        db.add(project)
        await db.flush()

        orch_session = await create_db_session(
            db,
            project_id=project.id,
            name=f"orchestrator-{project.id}",
            engine="claude_code",
            mode="orchestrator",
        )
        from codehive.core.task_queue import create_task

        task = await create_task(db, session_id=orch_session.id, title="Test task 3")
        await db.commit()

        @asynccontextmanager
        async def _factory():
            async with db_session_factory() as s:
                yield s

        orch = OrchestratorService(
            db_session_factory=_factory,
            project_id=project.id,
        )

        await orch._default_spawn_and_run(
            task_id=task.id,
            step="implementing",
            role="swe",
            mode="execution",
            instructions="do stuff",
            agent_profile_id=None,
        )

        async with _factory() as s:
            result = await s.execute(
                select(SessionModel).where(
                    SessionModel.task_id == task.id,
                    SessionModel.pipeline_step == "implementing",
                )
            )
            child = result.scalar_one()
            assert child.engine == "claude_code"


# ---------------------------------------------------------------------------
# Integration: API endpoints for preferred_engine / preferred_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTeamEngineAPI:
    async def test_post_team_member_with_engine(self, client: AsyncClient):
        """POST /api/projects/{id}/team with preferred_engine persists both fields."""
        resp = await client.post("/api/projects", json={"name": "engine-project"})
        project_id = resp.json()["id"]

        resp = await client.post(
            f"/api/projects/{project_id}/team",
            json={
                "name": "EngineAgent",
                "role": "swe",
                "preferred_engine": "codex",
                "preferred_model": "gpt-5.4",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["preferred_engine"] == "codex"
        assert data["preferred_model"] == "gpt-5.4"

    async def test_patch_team_member_engine(self, client: AsyncClient):
        """PATCH /api/projects/{id}/team/{agent_id} updates preferred_engine."""
        resp = await client.post("/api/projects", json={"name": "patch-engine"})
        project_id = resp.json()["id"]

        team_resp = await client.get(f"/api/projects/{project_id}/team")
        agent_id = team_resp.json()[0]["id"]

        resp = await client.patch(
            f"/api/projects/{project_id}/team/{agent_id}",
            json={"preferred_engine": "claude_code", "preferred_model": "claude-sonnet-4-6"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["preferred_engine"] == "claude_code"
        assert data["preferred_model"] == "claude-sonnet-4-6"

    async def test_patch_team_member_clear_engine(self, client: AsyncClient):
        """PATCH with preferred_engine: null clears the field."""
        resp = await client.post("/api/projects", json={"name": "clear-engine"})
        project_id = resp.json()["id"]

        # First set an engine
        team_resp = await client.get(f"/api/projects/{project_id}/team")
        agent_id = team_resp.json()[0]["id"]

        await client.patch(
            f"/api/projects/{project_id}/team/{agent_id}",
            json={"preferred_engine": "codex"},
        )

        # Now clear it
        resp = await client.patch(
            f"/api/projects/{project_id}/team/{agent_id}",
            json={"preferred_engine": None},
        )
        assert resp.status_code == 200
        assert resp.json()["preferred_engine"] is None

    async def test_get_team_returns_engine_fields(self, client: AsyncClient):
        """GET /api/projects/{id}/team returns preferred_engine and preferred_model."""
        resp = await client.post("/api/projects", json={"name": "get-engine"})
        project_id = resp.json()["id"]

        resp = await client.get(f"/api/projects/{project_id}/team")
        assert resp.status_code == 200
        team = resp.json()
        assert len(team) == 6
        for member in team:
            assert "preferred_engine" in member
            assert "preferred_model" in member
            assert member["preferred_engine"] is None
            assert member["preferred_model"] is None

    async def test_get_team_after_patch_persists_engine(self, client: AsyncClient):
        """GET after PATCH shows the updated engine in the team list."""
        resp = await client.post("/api/projects", json={"name": "persist-engine"})
        project_id = resp.json()["id"]

        team_resp = await client.get(f"/api/projects/{project_id}/team")
        agent_id = team_resp.json()[0]["id"]

        await client.patch(
            f"/api/projects/{project_id}/team/{agent_id}",
            json={"preferred_engine": "codex", "preferred_model": "gpt-5.4"},
        )

        resp = await client.get(f"/api/projects/{project_id}/team")
        updated = [m for m in resp.json() if m["id"] == agent_id]
        assert len(updated) == 1
        assert updated[0]["preferred_engine"] == "codex"
        assert updated[0]["preferred_model"] == "gpt-5.4"
