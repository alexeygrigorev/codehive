"""Tests for extended CLI commands: sessions pause/rollback, questions, system."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, MetaData, Table, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.cli import main
from codehive.db.models import Base, PendingQuestion, Project, Workspace
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


def _run_cli(args: list[str], monkeypatch: pytest.MonkeyPatch) -> tuple[str, int]:
    """Run the CLI with given args, capture stdout, return (output, exit_code)."""
    monkeypatch.setattr("sys.argv", ["codehive"] + args)
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)
    err = StringIO()
    monkeypatch.setattr("sys.stderr", err)
    try:
        main()
        return out.getvalue(), 0
    except SystemExit as e:
        return out.getvalue() + err.getvalue(), e.code or 0


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
        Table(table.name, metadata, *columns)
    return metadata


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    metadata = _sqlite_compatible_metadata()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(db_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with db_session_factory() as session:
        yield session


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
async def session_obj(db_session: AsyncSession, project: Project) -> SessionModel:
    sess = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="native",
        mode="execution",
        status="executing",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(sess)
    await db_session.commit()
    await db_session.refresh(sess)
    return sess


@pytest_asyncio.fixture
async def question_obj(db_session: AsyncSession, session_obj: SessionModel) -> PendingQuestion:
    pq = PendingQuestion(
        session_id=session_obj.id,
        question="Which database?",
        context=None,
        answered=False,
        answer=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(pq)
    await db_session.commit()
    await db_session.refresh(pq)
    return pq


@pytest_asyncio.fixture
async def api_client(
    db_session_factory,
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with db_session_factory() as session:
            yield session

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


# ===========================================================================
# Sessions pause: argument parsing and output
# ===========================================================================


class TestSessionsPauseArgParsing:
    def test_sessions_pause_parses_session_id(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": sess_id, "status": "idle"}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["sessions", "pause", sess_id], monkeypatch)

        assert code == 0
        assert f"Session {sess_id} paused." in output
        mock_client.post.assert_called_once_with(f"/api/sessions/{sess_id}/pause")

    def test_sessions_pause_409_invalid_state(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.json.return_value = {"detail": "Cannot pause from idle"}
        mock_resp.text = "Cannot pause from idle"

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["sessions", "pause", sess_id], monkeypatch)

        assert code != 0
        assert "Cannot pause from idle" in output

    def test_sessions_pause_404_not_found(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"detail": "Session not found"}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["sessions", "pause", sess_id], monkeypatch)

        assert code != 0
        assert "Session not found" in output


# ===========================================================================
# Sessions rollback: argument parsing and output
# ===========================================================================


class TestSessionsRollbackArgParsing:
    def test_sessions_rollback_parses_ids(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        cp_id = str(uuid.uuid4())

        list_resp = MagicMock()
        list_resp.status_code = 200
        list_resp.json.return_value = [{"id": cp_id, "session_id": sess_id}]

        rollback_resp = MagicMock()
        rollback_resp.status_code = 200
        rollback_resp.json.return_value = {"id": sess_id}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = list_resp
        mock_client.post.return_value = rollback_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(
                ["sessions", "rollback", sess_id, "--checkpoint", cp_id],
                monkeypatch,
            )

        assert code == 0
        assert f"Rolled back session {sess_id} to checkpoint {cp_id}." in output

    def test_sessions_rollback_missing_checkpoint_flag(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        output, code = _run_cli(["sessions", "rollback", sess_id], monkeypatch)
        assert code != 0

    def test_sessions_rollback_checkpoint_not_in_session(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        cp_id = str(uuid.uuid4())

        list_resp = MagicMock()
        list_resp.status_code = 200
        list_resp.json.return_value = [{"id": str(uuid.uuid4()), "session_id": sess_id}]

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = list_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(
                ["sessions", "rollback", sess_id, "--checkpoint", cp_id],
                monkeypatch,
            )

        assert code != 0
        assert "does not belong to session" in output

    def test_sessions_rollback_session_404(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        cp_id = str(uuid.uuid4())

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"detail": "Session not found"}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(
                ["sessions", "rollback", sess_id, "--checkpoint", cp_id],
                monkeypatch,
            )

        assert code != 0
        assert "Session not found" in output


# ===========================================================================
# Questions list: argument parsing and output
# ===========================================================================


class TestQuestionsListArgParsing:
    def test_questions_list_no_session(self, monkeypatch: pytest.MonkeyPatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["questions", "list"], monkeypatch)

        assert code == 0
        assert "No pending questions." in output
        mock_client.get.assert_called_once_with("/api/questions", params={"answered": "false"})

    def test_questions_list_with_session(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["questions", "list", "--session", sess_id], monkeypatch)

        assert code == 0
        assert "No pending questions." in output
        mock_client.get.assert_called_once_with(
            f"/api/sessions/{sess_id}/questions", params={"answered": "false"}
        )

    def test_questions_list_with_results(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        q_id1 = str(uuid.uuid4())
        q_id2 = str(uuid.uuid4())
        questions = [
            {
                "id": q_id1,
                "session_id": sess_id,
                "question": "Which DB?",
                "created_at": "2026-01-01T00:00:00",
            },
            {
                "id": q_id2,
                "session_id": sess_id,
                "question": "Which framework?",
                "created_at": "2026-01-02T00:00:00",
            },
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = questions

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["questions", "list"], monkeypatch)

        assert code == 0
        assert "ID" in output
        assert "Session" in output
        assert "Question" in output
        assert "Which DB?" in output
        assert "Which framework?" in output


# ===========================================================================
# Questions answer: argument parsing and output
# ===========================================================================


class TestQuestionsAnswerArgParsing:
    def test_questions_answer_success(self, monkeypatch: pytest.MonkeyPatch):
        q_id = str(uuid.uuid4())
        sess_id = str(uuid.uuid4())

        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {"id": q_id, "session_id": sess_id}

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.json.return_value = {"id": q_id, "answered": True}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = get_resp
        mock_client.post.return_value = post_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["questions", "answer", q_id, "use OAuth"], monkeypatch)

        assert code == 0
        assert f"Answered question {q_id}." in output
        # Verify the answer endpoint was called correctly
        mock_client.post.assert_called_once_with(
            f"/api/sessions/{sess_id}/questions/{q_id}/answer",
            json={"answer": "use OAuth"},
        )

    def test_questions_answer_409_already_answered(self, monkeypatch: pytest.MonkeyPatch):
        q_id = str(uuid.uuid4())
        sess_id = str(uuid.uuid4())

        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {"id": q_id, "session_id": sess_id}

        post_resp = MagicMock()
        post_resp.status_code = 409
        post_resp.json.return_value = {"detail": "Question already answered"}
        post_resp.text = "Question already answered"

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = get_resp
        mock_client.post.return_value = post_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["questions", "answer", q_id, "use OAuth"], monkeypatch)

        assert code != 0
        assert "Question already answered" in output

    def test_questions_answer_404_not_found(self, monkeypatch: pytest.MonkeyPatch):
        q_id = str(uuid.uuid4())

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"detail": "Question not found"}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["questions", "answer", q_id, "use OAuth"], monkeypatch)

        assert code != 0
        assert "Question not found" in output


# ===========================================================================
# System health: argument parsing and output
# ===========================================================================


class TestSystemHealthArgParsing:
    def test_system_health_success(self, monkeypatch: pytest.MonkeyPatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "version": "0.1.0",
            "database": "connected",
            "redis": "connected",
            "active_sessions": 3,
            "maintenance": False,
        }

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["system", "health"], monkeypatch)

        assert code == 0
        assert "Version:         0.1.0" in output
        assert "Database:        connected" in output
        assert "Redis:           connected" in output
        assert "Active sessions: 3" in output
        assert "Maintenance:     off" in output
        mock_client.get.assert_called_once_with("/api/system/health")

    def test_system_health_maintenance_on(self, monkeypatch: pytest.MonkeyPatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "version": "0.1.0",
            "database": "connected",
            "redis": "disconnected",
            "active_sessions": 0,
            "maintenance": True,
        }

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["system", "health"], monkeypatch)

        assert code == 0
        assert "Maintenance:     on" in output

    def test_system_health_connection_refused(self, monkeypatch: pytest.MonkeyPatch):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["system", "health"], monkeypatch)

        assert code != 0
        assert "Cannot connect to server" in output


# ===========================================================================
# System maintenance: argument parsing and output
# ===========================================================================


class TestSystemMaintenanceArgParsing:
    def test_system_maintenance_on(self, monkeypatch: pytest.MonkeyPatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"maintenance": True}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["system", "maintenance", "on"], monkeypatch)

        assert code == 0
        assert "Maintenance mode enabled." in output
        mock_client.post.assert_called_once_with("/api/system/maintenance", json={"enabled": True})

    def test_system_maintenance_off(self, monkeypatch: pytest.MonkeyPatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"maintenance": False}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["system", "maintenance", "off"], monkeypatch)

        assert code == 0
        assert "Maintenance mode disabled." in output
        mock_client.post.assert_called_once_with("/api/system/maintenance", json={"enabled": False})


# ===========================================================================
# Base URL: new commands respect --base-url and env var
# ===========================================================================


class TestBaseUrlNewCommands:
    def test_questions_list_base_url_override(self, monkeypatch: pytest.MonkeyPatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client) as mk:
            output, code = _run_cli(
                ["--base-url", "http://custom:9000", "questions", "list"],
                monkeypatch,
            )

        assert code == 0
        mk.assert_called_once_with("http://custom:9000")

    def test_system_health_env_var(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("CODEHIVE_BASE_URL", "http://env-host:8080")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "version": "0.1.0",
            "database": "connected",
            "redis": "disconnected",
            "active_sessions": 0,
            "maintenance": False,
        }

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client) as mk:
            output, code = _run_cli(["system", "health"], monkeypatch)

        assert code == 0
        mk.assert_called_once_with("http://env-host:8080")


# ===========================================================================
# Integration: GET /api/questions and GET /api/questions/{id}
# ===========================================================================


@pytest.mark.asyncio
class TestGlobalQuestionsEndpoints:
    async def test_list_questions_empty(self, api_client: AsyncClient):
        resp = await api_client.get("/api/questions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_questions_returns_all(
        self, api_client: AsyncClient, question_obj: PendingQuestion
    ):
        resp = await api_client.get("/api/questions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["id"] == str(question_obj.id)
        assert data[0]["session_id"] == str(question_obj.session_id)

    async def test_list_questions_filter_unanswered(
        self, api_client: AsyncClient, question_obj: PendingQuestion
    ):
        resp = await api_client.get("/api/questions?answered=false")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all(q["answered"] is False for q in data)

    async def test_list_questions_filter_answered(
        self, api_client: AsyncClient, question_obj: PendingQuestion
    ):
        resp = await api_client.get("/api/questions?answered=true")
        assert resp.status_code == 200
        data = resp.json()
        # question_obj is unanswered, so filtering for answered=true should not include it
        assert all(q["answered"] is True for q in data)

    async def test_get_question_by_id(self, api_client: AsyncClient, question_obj: PendingQuestion):
        resp = await api_client.get(f"/api/questions/{question_obj.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(question_obj.id)
        assert data["question"] == "Which database?"

    async def test_get_question_not_found(self, api_client: AsyncClient):
        resp = await api_client.get(f"/api/questions/{uuid.uuid4()}")
        assert resp.status_code == 404


# ===========================================================================
# Integration: GET /api/system/health and POST /api/system/maintenance
# ===========================================================================


@pytest.mark.asyncio
class TestSystemEndpoints:
    async def test_system_health(self, api_client: AsyncClient):
        resp = await api_client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "database" in data
        assert "redis" in data
        assert "active_sessions" in data
        assert "maintenance" in data
        assert data["database"] == "connected"
        assert isinstance(data["active_sessions"], int)

    async def test_system_health_active_sessions_count(
        self, api_client: AsyncClient, session_obj: SessionModel
    ):
        """session_obj has status='executing' so it should be counted."""
        resp = await api_client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_sessions"] >= 1

    async def test_maintenance_toggle_on(self, api_client: AsyncClient):
        resp = await api_client.post("/api/system/maintenance", json={"enabled": True})
        assert resp.status_code == 200
        assert resp.json()["maintenance"] is True

        # Health should reflect maintenance
        resp = await api_client.get("/api/system/health")
        assert resp.json()["maintenance"] is True

    async def test_maintenance_toggle_off(self, api_client: AsyncClient):
        # Turn on first
        await api_client.post("/api/system/maintenance", json={"enabled": True})
        # Turn off
        resp = await api_client.post("/api/system/maintenance", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["maintenance"] is False

        resp = await api_client.get("/api/system/health")
        assert resp.json()["maintenance"] is False
