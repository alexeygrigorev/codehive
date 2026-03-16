"""Tests for the new-project flow (issue #55a)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import JSON, MetaData, Table, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.api.schemas.project_flow import (
    FlowType,
    ProjectBrief,
    ProjectFlowStart,
    SuggestedSession,
)
from codehive.core.project_flow import (
    FlowAlreadyFinalizedError,
    FlowNotFoundError,
    _reset_flow_states,
    finalize_flow,
    generate_brief,
    respond_to_flow,
    start_flow,
)
from codehive.db.models import Base, Workspace

# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


def _sqlite_compatible_metadata() -> MetaData:
    """Return a copy of Base.metadata with SQLite-compatible types and defaults."""
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
        _reset_flow_states()
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


# ---------------------------------------------------------------------------
# Unit tests: Schema validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_project_flow_start_rejects_missing_flow_type(self):
        with pytest.raises(ValidationError):
            ProjectFlowStart(workspace_id=uuid.uuid4())  # type: ignore[call-arg]

    def test_project_flow_start_rejects_invalid_flow_type(self):
        with pytest.raises(ValidationError):
            ProjectFlowStart(
                flow_type="invalid_type",  # type: ignore[arg-type]
                workspace_id=uuid.uuid4(),
            )

    def test_project_brief_validates_name_nonempty(self):
        with pytest.raises(ValidationError):
            ProjectBrief(
                name="",
                description="desc",
                tech_stack={},
                architecture={},
                open_decisions=[],
                suggested_sessions=[],
            )

    def test_project_brief_validates_description_nonempty(self):
        with pytest.raises(ValidationError):
            ProjectBrief(
                name="proj",
                description="",
                tech_stack={},
                architecture={},
                open_decisions=[],
                suggested_sessions=[],
            )

    def test_suggested_session_validates_mode(self):
        with pytest.raises(ValidationError):
            SuggestedSession(name="s1", mission="do stuff", mode="invalid_mode")

    def test_suggested_session_accepts_valid_mode(self):
        s = SuggestedSession(name="s1", mission="do stuff", mode="execution")
        assert s.mode == "execution"


# ---------------------------------------------------------------------------
# Unit tests: Flow creation and state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFlowCreation:
    async def test_start_interview_flow(self, db_session: AsyncSession, workspace: Workspace):
        flow_id, session_id, questions = await start_flow(
            db_session,
            flow_type=FlowType.interview,
            workspace_id=workspace.id,
            initial_input="Build a task manager",
        )
        assert isinstance(flow_id, uuid.UUID)
        assert isinstance(session_id, uuid.UUID)
        assert 3 <= len(questions) <= 7
        for q in questions:
            assert q.id
            assert q.text
            assert q.category

    async def test_start_brainstorm_flow(self, db_session: AsyncSession, workspace: Workspace):
        flow_id, session_id, questions = await start_flow(
            db_session,
            flow_type=FlowType.brainstorm,
            workspace_id=workspace.id,
        )
        assert isinstance(flow_id, uuid.UUID)
        assert len(questions) >= 1

    async def test_start_spec_from_notes_short_input(
        self, db_session: AsyncSession, workspace: Workspace
    ):
        flow_id, session_id, questions = await start_flow(
            db_session,
            flow_type=FlowType.spec_from_notes,
            workspace_id=workspace.id,
            initial_input="short",
        )
        # Short notes should get clarifying questions
        assert len(questions) >= 1

    async def test_start_spec_from_notes_long_input(
        self, db_session: AsyncSession, workspace: Workspace
    ):
        long_input = "A" * 100 + " Build a web application with React frontend and Python backend"
        flow_id, session_id, questions = await start_flow(
            db_session,
            flow_type=FlowType.spec_from_notes,
            workspace_id=workspace.id,
            initial_input=long_input,
        )
        # Long enough notes produce no clarifying questions
        assert questions == []

    async def test_start_from_repo_calls_analyze(
        self, db_session: AsyncSession, workspace: Workspace
    ):
        """start_from_repo invokes analyze_codebase and includes follow-up questions."""
        flow_id, session_id, questions = await start_flow(
            db_session,
            flow_type=FlowType.start_from_repo,
            workspace_id=workspace.id,
            initial_input="/nonexistent/path",
        )
        # With a non-existent path, analysis is empty, so we get tech stack question
        assert any(q.category == "tech" or q.category == "goals" for q in questions)


# ---------------------------------------------------------------------------
# Unit tests: Brief generation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBriefGeneration:
    async def test_generate_brief_returns_all_fields(self):
        state = {
            "answers_received": [
                {"question_id": "q1", "answer": "Build a task manager"},
                {"question_id": "q3", "answer": "Python and React"},
            ],
            "analysis": {},
            "initial_input": "",
        }
        brief = await generate_brief(state)
        assert brief.name
        assert brief.description
        assert isinstance(brief.tech_stack, dict)
        assert isinstance(brief.architecture, dict)
        assert isinstance(brief.open_decisions, list)
        assert len(brief.suggested_sessions) > 0
        for s in brief.suggested_sessions:
            assert s.name
            assert s.mission
            assert s.mode

    async def test_generate_brief_open_decisions_list(self):
        state = {
            "answers_received": [
                {"question_id": "q1", "answer": "Test project"},
            ],
            "analysis": {},
            "initial_input": "",
        }
        brief = await generate_brief(state)
        assert isinstance(brief.open_decisions, list)

    async def test_generate_brief_archetype_null_or_valid(self):
        state = {
            "answers_received": [
                {"question_id": "q1", "answer": "Test project"},
            ],
            "analysis": {},
            "initial_input": "",
        }
        brief = await generate_brief(state)
        # For now it's always None
        assert brief.suggested_archetype is None


# ---------------------------------------------------------------------------
# Unit tests: Respond and finalize
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRespondAndFinalize:
    async def test_respond_nonexistent_flow(self):
        with pytest.raises(FlowNotFoundError):
            await respond_to_flow(uuid.uuid4(), [])

    async def test_respond_interview_produces_brief(
        self, db_session: AsyncSession, workspace: Workspace
    ):
        flow_id, _, _ = await start_flow(
            db_session,
            flow_type=FlowType.interview,
            workspace_id=workspace.id,
        )
        next_q, brief = await respond_to_flow(
            flow_id,
            [{"question_id": "q1", "answer": "Build a task manager"}],
        )
        # Interview has single round, so brief should be produced
        assert next_q is None
        assert brief is not None
        assert brief.name

    async def test_respond_brainstorm_has_followup(
        self, db_session: AsyncSession, workspace: Workspace
    ):
        flow_id, _, _ = await start_flow(
            db_session,
            flow_type=FlowType.brainstorm,
            workspace_id=workspace.id,
        )
        next_q, brief = await respond_to_flow(
            flow_id,
            [{"question_id": "b1", "answer": "I want to build a social app"}],
        )
        # First round of brainstorm should produce follow-up questions
        assert next_q is not None
        assert brief is None
        assert len(next_q) >= 1

    async def test_finalize_creates_project_and_sessions(
        self, db_session: AsyncSession, workspace: Workspace
    ):
        flow_id, _, _ = await start_flow(
            db_session,
            flow_type=FlowType.interview,
            workspace_id=workspace.id,
        )
        await respond_to_flow(
            flow_id,
            [{"question_id": "q1", "answer": "My Cool Project"}],
        )
        project_id, sessions = await finalize_flow(db_session, flow_id)
        assert isinstance(project_id, uuid.UUID)
        assert len(sessions) > 0
        for s in sessions:
            assert isinstance(s["id"], uuid.UUID)
            assert s["name"]
            assert s["mode"]

    async def test_finalize_already_finalized_raises(
        self, db_session: AsyncSession, workspace: Workspace
    ):
        flow_id, _, _ = await start_flow(
            db_session,
            flow_type=FlowType.interview,
            workspace_id=workspace.id,
        )
        await respond_to_flow(
            flow_id,
            [{"question_id": "q1", "answer": "Project X"}],
        )
        await finalize_flow(db_session, flow_id)
        with pytest.raises(FlowAlreadyFinalizedError):
            await finalize_flow(db_session, flow_id)

    async def test_finalize_writes_knowledge(self, db_session: AsyncSession, workspace: Workspace):
        flow_id, _, _ = await start_flow(
            db_session,
            flow_type=FlowType.interview,
            workspace_id=workspace.id,
        )
        await respond_to_flow(
            flow_id,
            [
                {"question_id": "q1", "answer": "Task Manager"},
                {"question_id": "q3", "answer": "Python FastAPI"},
            ],
        )
        project_id, _ = await finalize_flow(db_session, flow_id)

        from codehive.core.knowledge import get_knowledge

        knowledge = await get_knowledge(db_session, project_id)
        assert "tech_stack" in knowledge
        assert "architecture" in knowledge
        assert "open_decisions" in knowledge


# ---------------------------------------------------------------------------
# Integration tests: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestProjectFlowAPI:
    async def test_start_interview_200(self, client: AsyncClient, workspace: Workspace):
        resp = await client.post(
            "/api/project-flow/start",
            json={
                "flow_type": "interview",
                "workspace_id": str(workspace.id),
                "initial_input": "Build a web app",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "flow_id" in data
        assert "session_id" in data
        assert "first_questions" in data
        assert 3 <= len(data["first_questions"]) <= 7
        for q in data["first_questions"]:
            assert "id" in q
            assert "text" in q
            assert "category" in q

    async def test_start_brainstorm_200(self, client: AsyncClient, workspace: Workspace):
        resp = await client.post(
            "/api/project-flow/start",
            json={
                "flow_type": "brainstorm",
                "workspace_id": str(workspace.id),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["first_questions"]) >= 1

    async def test_start_invalid_flow_type_422(self, client: AsyncClient, workspace: Workspace):
        resp = await client.post(
            "/api/project-flow/start",
            json={
                "flow_type": "totally_invalid",
                "workspace_id": str(workspace.id),
            },
        )
        assert resp.status_code == 422

    async def test_respond_200(self, client: AsyncClient, workspace: Workspace):
        start_resp = await client.post(
            "/api/project-flow/start",
            json={
                "flow_type": "interview",
                "workspace_id": str(workspace.id),
            },
        )
        flow_id = start_resp.json()["flow_id"]

        resp = await client.post(
            f"/api/project-flow/{flow_id}/respond",
            json={
                "answers": [{"question_id": "q1", "answer": "Build a web app"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # Interview produces brief on first respond
        assert data["brief"] is not None
        assert data["next_questions"] is None

    async def test_respond_nonexistent_flow_404(self, client: AsyncClient):
        resp = await client.post(
            f"/api/project-flow/{uuid.uuid4()}/respond",
            json={"answers": []},
        )
        assert resp.status_code == 404

    async def test_finalize_200(self, client: AsyncClient, workspace: Workspace):
        start_resp = await client.post(
            "/api/project-flow/start",
            json={
                "flow_type": "interview",
                "workspace_id": str(workspace.id),
            },
        )
        flow_id = start_resp.json()["flow_id"]

        await client.post(
            f"/api/project-flow/{flow_id}/respond",
            json={
                "answers": [{"question_id": "q1", "answer": "Task Manager Pro"}],
            },
        )

        resp = await client.post(f"/api/project-flow/{flow_id}/finalize")
        assert resp.status_code == 200
        data = resp.json()
        assert "project_id" in data
        assert "sessions" in data
        assert len(data["sessions"]) > 0
        for s in data["sessions"]:
            assert "id" in s
            assert "name" in s
            assert "mode" in s

    async def test_finalize_already_finalized_409(self, client: AsyncClient, workspace: Workspace):
        start_resp = await client.post(
            "/api/project-flow/start",
            json={
                "flow_type": "interview",
                "workspace_id": str(workspace.id),
            },
        )
        flow_id = start_resp.json()["flow_id"]

        await client.post(
            f"/api/project-flow/{flow_id}/respond",
            json={
                "answers": [{"question_id": "q1", "answer": "Proj"}],
            },
        )
        resp1 = await client.post(f"/api/project-flow/{flow_id}/finalize")
        assert resp1.status_code == 200

        resp2 = await client.post(f"/api/project-flow/{flow_id}/finalize")
        assert resp2.status_code == 409

    async def test_full_flow_end_to_end(self, client: AsyncClient, workspace: Workspace):
        """Full flow: start -> respond -> finalize, verify project and sessions."""
        # Start
        start_resp = await client.post(
            "/api/project-flow/start",
            json={
                "flow_type": "interview",
                "workspace_id": str(workspace.id),
                "initial_input": "Build a task tracking app",
            },
        )
        assert start_resp.status_code == 200
        flow_id = start_resp.json()["flow_id"]

        # Respond
        respond_resp = await client.post(
            f"/api/project-flow/{flow_id}/respond",
            json={
                "answers": [
                    {"question_id": "q1", "answer": "Task Tracker App"},
                    {"question_id": "q3", "answer": "Python with FastAPI backend"},
                ],
            },
        )
        assert respond_resp.status_code == 200
        brief = respond_resp.json()["brief"]
        assert brief is not None
        assert brief["name"]
        assert brief["description"]
        assert isinstance(brief["tech_stack"], dict)
        assert isinstance(brief["suggested_sessions"], list)

        # Finalize
        finalize_resp = await client.post(f"/api/project-flow/{flow_id}/finalize")
        assert finalize_resp.status_code == 200
        data = finalize_resp.json()

        project_id = data["project_id"]
        assert project_id

        # Verify project exists with correct knowledge
        proj_resp = await client.get(f"/api/projects/{project_id}")
        assert proj_resp.status_code == 200
        proj_data = proj_resp.json()
        assert "tech_stack" in proj_data["knowledge"]
        assert "architecture" in proj_data["knowledge"]
        assert "open_decisions" in proj_data["knowledge"]

    async def test_start_spec_from_notes_200(self, client: AsyncClient, workspace: Workspace):
        resp = await client.post(
            "/api/project-flow/start",
            json={
                "flow_type": "spec_from_notes",
                "workspace_id": str(workspace.id),
                "initial_input": "A web application for managing tasks with user auth, CRUD, etc.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "flow_id" in data
        assert "first_questions" in data

    async def test_start_from_repo_200(self, client: AsyncClient, workspace: Workspace):
        resp = await client.post(
            "/api/project-flow/start",
            json={
                "flow_type": "start_from_repo",
                "workspace_id": str(workspace.id),
                "initial_input": "/nonexistent/path",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "flow_id" in data
        assert len(data["first_questions"]) >= 1
