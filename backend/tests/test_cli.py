"""Tests for CLI session and project commands."""

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
from codehive.db.models import Base, Project, Workspace
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
    """Return a copy of Base.metadata with SQLite-compatible types."""
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
            columns.append(col_copy)
        Table(table.name, metadata, *columns)
    return metadata


# ---------------------------------------------------------------------------
# Fixtures for integration tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite async engine with tables."""
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
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(sess)
    await db_session.commit()
    await db_session.refresh(sess)
    return sess


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
        yield ac


# ---------------------------------------------------------------------------
# Argument parsing tests
# ---------------------------------------------------------------------------


class TestProjectsArgParsing:
    def test_projects_list_parses(self, monkeypatch: pytest.MonkeyPatch):
        """projects list calls GET /api/projects."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["projects", "list"], monkeypatch)

        assert code == 0
        assert "No projects found." in output
        mock_client.get.assert_called_once_with("/api/projects")

    def test_projects_create_parses_name_and_workspace(self, monkeypatch: pytest.MonkeyPatch):
        ws_id = str(uuid.uuid4())
        proj_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"name": "myproject", "id": proj_id}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(
                ["projects", "create", "myproject", "--workspace", ws_id],
                monkeypatch,
            )

        assert code == 0
        assert "Created project myproject" in output
        assert proj_id in output
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/api/projects"
        body = call_args[1]["json"]
        assert body["name"] == "myproject"
        assert body["workspace_id"] == ws_id

    def test_projects_create_missing_workspace_errors(self, monkeypatch: pytest.MonkeyPatch):
        """Missing --workspace should cause argparse error."""
        output, code = _run_cli(["projects", "create", "myproject"], monkeypatch)
        assert code != 0


class TestSessionsArgParsing:
    def test_sessions_list_parses_project(self, monkeypatch: pytest.MonkeyPatch):
        proj_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["sessions", "list", "--project", proj_id], monkeypatch)

        assert code == 0
        assert "No sessions found." in output
        mock_client.get.assert_called_once_with(f"/api/projects/{proj_id}/sessions")

    def test_sessions_list_missing_project_errors(self, monkeypatch: pytest.MonkeyPatch):
        output, code = _run_cli(["sessions", "list"], monkeypatch)
        assert code != 0

    def test_sessions_create_defaults(self, monkeypatch: pytest.MonkeyPatch):
        proj_id = str(uuid.uuid4())
        sess_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"name": "mysession", "id": sess_id}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(
                ["sessions", "create", proj_id, "--name", "mysession"],
                monkeypatch,
            )

        assert code == 0
        assert "Created session mysession" in output
        body = mock_client.post.call_args[1]["json"]
        assert body["engine"] == "native"
        assert body["mode"] == "execution"

    def test_sessions_create_custom_engine_mode(self, monkeypatch: pytest.MonkeyPatch):
        proj_id = str(uuid.uuid4())
        sess_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"name": "mysession", "id": sess_id}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(
                [
                    "sessions",
                    "create",
                    proj_id,
                    "--name",
                    "mysession",
                    "--engine",
                    "claude_code",
                    "--mode",
                    "brainstorm",
                ],
                monkeypatch,
            )

        assert code == 0
        body = mock_client.post.call_args[1]["json"]
        assert body["engine"] == "claude_code"
        assert body["mode"] == "brainstorm"

    def test_sessions_status_parses_session_id(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": sess_id,
            "name": "test-session",
            "project_id": str(uuid.uuid4()),
            "engine": "native",
            "mode": "execution",
            "status": "idle",
            "created_at": "2026-01-01T00:00:00",
        }

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["sessions", "status", sess_id], monkeypatch)

        assert code == 0
        assert "test-session" in output
        assert "idle" in output
        assert "native" in output
        assert "execution" in output

    def test_sessions_chat_parses_session_id(self, monkeypatch: pytest.MonkeyPatch):
        """Chat should verify session then enter REPL; EOF exits cleanly."""
        sess_id = str(uuid.uuid4())
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {
            "id": sess_id,
            "name": "chat-session",
            "status": "idle",
        }

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = get_resp

        monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(EOFError))

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["sessions", "chat", sess_id], monkeypatch)

        assert code == 0
        assert "chat-session" in output


class TestBaseUrlFlag:
    def test_base_url_override(self, monkeypatch: pytest.MonkeyPatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client) as mk:
            output, code = _run_cli(
                ["--base-url", "http://example.com", "projects", "list"],
                monkeypatch,
            )

        assert code == 0
        mk.assert_called_once_with("http://example.com")

    def test_base_url_from_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("CODEHIVE_BASE_URL", "http://env-server:9000")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client) as mk:
            output, code = _run_cli(["projects", "list"], monkeypatch)

        assert code == 0
        mk.assert_called_once_with("http://env-server:9000")


# ---------------------------------------------------------------------------
# Output formatting tests
# ---------------------------------------------------------------------------


class TestOutputFormatting:
    def test_projects_list_table(self, monkeypatch: pytest.MonkeyPatch):
        projects = [
            {
                "id": str(uuid.uuid4()),
                "name": "proj1",
                "path": "/home/proj1",
                "created_at": "2026-01-01T00:00:00",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "proj2",
                "path": "/home/proj2",
                "created_at": "2026-01-02T00:00:00",
            },
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = projects

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["projects", "list"], monkeypatch)

        assert code == 0
        assert "ID" in output
        assert "Name" in output
        assert "proj1" in output
        assert "proj2" in output

    def test_sessions_list_table(self, monkeypatch: pytest.MonkeyPatch):
        proj_id = str(uuid.uuid4())
        sessions = [
            {
                "id": str(uuid.uuid4()),
                "name": "s1",
                "engine": "native",
                "mode": "execution",
                "status": "idle",
                "created_at": "2026-01-01T00:00:00",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "s2",
                "engine": "claude_code",
                "mode": "brainstorm",
                "status": "running",
                "created_at": "2026-01-02T00:00:00",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "s3",
                "engine": "native",
                "mode": "execution",
                "status": "blocked",
                "created_at": "2026-01-03T00:00:00",
            },
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = sessions

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["sessions", "list", "--project", proj_id], monkeypatch)

        assert code == 0
        assert "ID" in output
        assert "Name" in output
        assert "s1" in output
        assert "s2" in output
        assert "s3" in output

    def test_projects_create_success_message(self, monkeypatch: pytest.MonkeyPatch):
        ws_id = str(uuid.uuid4())
        proj_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"name": "newproj", "id": proj_id}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(
                ["projects", "create", "newproj", "--workspace", ws_id],
                monkeypatch,
            )

        assert code == 0
        assert f"Created project newproj ({proj_id})" in output

    def test_sessions_create_success_message(self, monkeypatch: pytest.MonkeyPatch):
        proj_id = str(uuid.uuid4())
        sess_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"name": "newsess", "id": sess_id}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(
                ["sessions", "create", proj_id, "--name", "newsess"],
                monkeypatch,
            )

        assert code == 0
        assert f"Created session newsess ({sess_id})" in output


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_connection_refused(self, monkeypatch: pytest.MonkeyPatch):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["projects", "list"], monkeypatch)

        assert code != 0
        assert "Cannot connect to server" in output

    def test_api_404_error(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"detail": "Session not found"}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["sessions", "status", sess_id], monkeypatch)

        assert code != 0
        assert "Session not found" in output

    def test_api_422_error(self, monkeypatch: pytest.MonkeyPatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.json.return_value = {"detail": "Invalid input"}

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_resp

        ws_id = str(uuid.uuid4())
        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(
                ["projects", "create", "test", "--workspace", ws_id],
                monkeypatch,
            )

        assert code != 0
        assert "Validation error" in output


# ---------------------------------------------------------------------------
# Chat REPL tests
# ---------------------------------------------------------------------------


class TestChatREPL:
    def test_chat_send_and_receive(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {
            "id": sess_id,
            "name": "chat-session",
            "status": "idle",
        }

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.json.return_value = [
            {"type": "message.created", "role": "user", "content": "hello"},
            {
                "type": "message.created",
                "role": "assistant",
                "content": "Hello! How can I help?",
            },
        ]

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = get_resp
        mock_client.post.return_value = post_resp

        inputs = iter(["hello"])

        def fake_input(prompt: str) -> str:
            try:
                return next(inputs)
            except StopIteration:
                raise EOFError

        monkeypatch.setattr("builtins.input", fake_input)

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["sessions", "chat", sess_id], monkeypatch)

        assert code == 0
        assert "Hello! How can I help?" in output

    def test_chat_eof_exits(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {
            "id": sess_id,
            "name": "chat-session",
            "status": "idle",
        }

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = get_resp

        monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(EOFError))

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["sessions", "chat", sess_id], monkeypatch)

        assert code == 0

    def test_chat_quit_exits(self, monkeypatch: pytest.MonkeyPatch):
        sess_id = str(uuid.uuid4())
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {
            "id": sess_id,
            "name": "chat-session",
            "status": "idle",
        }

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = get_resp

        inputs = iter(["/quit"])

        def fake_input(prompt: str) -> str:
            try:
                return next(inputs)
            except StopIteration:
                raise EOFError

        monkeypatch.setattr("builtins.input", fake_input)

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(["sessions", "chat", sess_id], monkeypatch)

        assert code == 0
        mock_client.post.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: Messages API endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMessagesEndpointIntegration:
    """Integration tests for POST /api/sessions/{id}/messages."""

    async def test_messages_nonexistent_session_404(self, api_client: AsyncClient):
        resp = await api_client.post(
            f"/api/sessions/{uuid.uuid4()}/messages",
            json={"content": "hello"},
        )
        assert resp.status_code == 404

    async def test_messages_missing_content_422(self, api_client: AsyncClient):
        resp = await api_client.post(
            f"/api/sessions/{uuid.uuid4()}/messages",
            json={},
        )
        assert resp.status_code == 422

    async def test_messages_success_with_mocked_engine(
        self, api_client: AsyncClient, session_obj: SessionModel
    ):
        fake_events = [
            {"type": "message.created", "role": "user", "content": "hello"},
            {"type": "message.created", "role": "assistant", "content": "Hi there!"},
        ]

        async def fake_send_message(*args, **kwargs):
            for ev in fake_events:
                yield ev

        mock_engine = MagicMock()
        mock_engine.send_message = fake_send_message

        async def mock_build_engine(session_config):
            return mock_engine

        with patch(
            "codehive.api.routes.sessions._build_engine",
            side_effect=mock_build_engine,
        ):
            resp = await api_client.post(
                f"/api/sessions/{session_obj.id}/messages",
                json={"content": "hello"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[1]["type"] == "message.created"
        assert data[1]["role"] == "assistant"
        assert data[1]["content"] == "Hi there!"

    async def test_messages_engine_error_500(
        self, api_client: AsyncClient, session_obj: SessionModel
    ):
        async def failing_send(*args, **kwargs):
            raise RuntimeError("Engine exploded")
            yield  # pragma: no cover

        mock_engine = MagicMock()
        mock_engine.send_message = failing_send

        async def mock_build_engine(session_config):
            return mock_engine

        with patch(
            "codehive.api.routes.sessions._build_engine",
            side_effect=mock_build_engine,
        ):
            resp = await api_client.post(
                f"/api/sessions/{session_obj.id}/messages",
                json={"content": "hello"},
            )

        assert resp.status_code == 500
        assert "Engine exploded" in resp.json()["detail"]
