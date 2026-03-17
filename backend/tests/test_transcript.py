"""Tests for TranscriptService and transcript REST endpoint."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.events import SessionNotFoundError
from codehive.core.transcript import TranscriptService
from codehive.db.models import Base, Event, Message, Project, Workspace
from codehive.db.models import Session as SessionModel

# Tests that use auth-protected endpoints require auth_enabled=True.
pytestmark = pytest.mark.usefixtures("_enable_auth")


@pytest.fixture(autouse=True)
def _enable_auth(monkeypatch):
    """Ensure auth is enabled for all tests in this module."""
    monkeypatch.setenv("CODEHIVE_AUTH_ENABLED", "true")


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
async def session_model(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="native",
        mode="execution",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def transcript_service() -> TranscriptService:
    return TranscriptService()


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
# Helpers
# ---------------------------------------------------------------------------

BASE_TIME = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


async def _seed_messages(
    db: AsyncSession,
    session_id: uuid.UUID,
    messages: list[tuple[str, str]],
    *,
    base_time: datetime = BASE_TIME,
) -> list[Message]:
    """Seed messages with incrementing timestamps. Each item is (role, content)."""
    created = []
    for i, (role, content) in enumerate(messages):
        msg = Message(
            session_id=session_id,
            role=role,
            content=content,
            metadata_={},
            created_at=base_time + timedelta(seconds=i * 10),
        )
        db.add(msg)
        created.append(msg)
    await db.commit()
    for msg in created:
        await db.refresh(msg)
    return created


async def _seed_tool_events(
    db: AsyncSession,
    session_id: uuid.UUID,
    tool_calls: list[tuple[str, str, str, bool]],
    *,
    base_time: datetime = BASE_TIME,
) -> list[Event]:
    """Seed paired tool events. Each item is (call_id, tool_name, output, is_error)."""
    created = []
    for i, (call_id, tool_name, output, is_error) in enumerate(tool_calls):
        offset = timedelta(seconds=i * 10 + 5)  # interleave with messages
        start = Event(
            session_id=session_id,
            type="tool.call.started",
            data={"call_id": call_id, "tool_name": tool_name, "input": f"input-{call_id}"},
            created_at=base_time + offset,
        )
        db.add(start)
        created.append(start)

        finish = Event(
            session_id=session_id,
            type="tool.call.finished",
            data={"call_id": call_id, "output": output, "is_error": is_error},
            created_at=base_time + offset + timedelta(seconds=2),
        )
        db.add(finish)
        created.append(finish)

    await db.commit()
    for ev in created:
        await db.refresh(ev)
    return created


# ---------------------------------------------------------------------------
# Unit tests: TranscriptService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTranscriptServiceBuild:
    async def test_messages_only(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        transcript_service: TranscriptService,
    ):
        """Build transcript with only messages returns all messages in order."""
        await _seed_messages(
            db_session,
            session_model.id,
            [("user", "Hello"), ("assistant", "Hi there")],
        )
        result = await transcript_service.render_json(db_session, session_model.id)
        assert result["entry_count"] == 2
        assert result["entries"][0]["type"] == "message"
        assert result["entries"][0]["role"] == "user"
        assert result["entries"][0]["content"] == "Hello"
        assert result["entries"][1]["role"] == "assistant"

    async def test_messages_and_tool_calls_interleaved(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        transcript_service: TranscriptService,
    ):
        """Build transcript with messages and tool calls interleaves chronologically."""
        await _seed_messages(
            db_session,
            session_model.id,
            [("user", "Do something")],
        )
        await _seed_tool_events(
            db_session,
            session_model.id,
            [("c1", "edit_file", "done", False)],
        )
        result = await transcript_service.render_json(db_session, session_model.id)
        assert result["entry_count"] == 2
        # Message at t+0, tool call at t+5
        assert result["entries"][0]["type"] == "message"
        assert result["entries"][1]["type"] == "tool_call"

    async def test_empty_session(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        transcript_service: TranscriptService,
    ):
        """Build transcript for a session with no messages or events returns empty entries."""
        result = await transcript_service.render_json(db_session, session_model.id)
        assert result["entry_count"] == 0
        assert result["entries"] == []
        assert result["session_name"] == "test-session"

    async def test_nonexistent_session(
        self,
        db_session: AsyncSession,
        transcript_service: TranscriptService,
    ):
        """Build transcript for non-existent session raises SessionNotFoundError."""
        with pytest.raises(SessionNotFoundError):
            await transcript_service.render_json(db_session, uuid.uuid4())


@pytest.mark.asyncio
class TestTranscriptRenderMarkdown:
    async def test_includes_session_header(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        transcript_service: TranscriptService,
    ):
        """render_markdown includes session name and status in header."""
        md = await transcript_service.render_markdown(db_session, session_model.id)
        assert "# Session: test-session" in md
        assert "**Status:** idle" in md
        assert "**Engine:** native" in md
        assert "**Mode:** execution" in md

    async def test_user_message_format(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        transcript_service: TranscriptService,
    ):
        """render_markdown formats user messages with User role heading."""
        await _seed_messages(db_session, session_model.id, [("user", "Hello world")])
        md = await transcript_service.render_markdown(db_session, session_model.id)
        assert "### User (" in md
        assert "Hello world" in md

    async def test_assistant_message_format(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        transcript_service: TranscriptService,
    ):
        """render_markdown formats assistant messages with Assistant role heading."""
        await _seed_messages(db_session, session_model.id, [("assistant", "I can help")])
        md = await transcript_service.render_markdown(db_session, session_model.id)
        assert "### Assistant (" in md
        assert "I can help" in md

    async def test_tool_call_format(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        transcript_service: TranscriptService,
    ):
        """render_markdown formats tool calls as fenced code blocks."""
        await _seed_tool_events(
            db_session,
            session_model.id,
            [("c1", "edit_file", "file edited", False)],
        )
        md = await transcript_service.render_markdown(db_session, session_model.id)
        assert "### Tool Call: edit_file" in md
        assert "```" in md
        assert "input-c1" in md
        assert "file edited" in md

    async def test_nonexistent_session(
        self,
        db_session: AsyncSession,
        transcript_service: TranscriptService,
    ):
        """render_markdown raises SessionNotFoundError for non-existent session."""
        with pytest.raises(SessionNotFoundError):
            await transcript_service.render_markdown(db_session, uuid.uuid4())


@pytest.mark.asyncio
class TestTranscriptRenderJSON:
    async def test_json_structure(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        transcript_service: TranscriptService,
    ):
        """render_json returns dict with expected metadata fields."""
        result = await transcript_service.render_json(db_session, session_model.id)
        assert result["session_id"] == session_model.id
        assert result["session_name"] == "test-session"
        assert result["status"] == "idle"
        assert result["engine"] == "native"
        assert result["mode"] == "execution"
        assert "created_at" in result
        assert "exported_at" in result
        assert result["entry_count"] == 0
        assert result["entries"] == []

    async def test_message_entry_structure(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        transcript_service: TranscriptService,
    ):
        """render_json entry for a message has type=message, role, content, timestamp."""
        await _seed_messages(db_session, session_model.id, [("user", "test content")])
        result = await transcript_service.render_json(db_session, session_model.id)
        entry = result["entries"][0]
        assert entry["type"] == "message"
        assert entry["role"] == "user"
        assert entry["content"] == "test content"
        assert "timestamp" in entry

    async def test_tool_call_entry_structure(
        self,
        db_session: AsyncSession,
        session_model: SessionModel,
        transcript_service: TranscriptService,
    ):
        """render_json entry for a tool call has type=tool_call, tool_name, input, output, is_error."""
        await _seed_tool_events(
            db_session,
            session_model.id,
            [("c1", "read_file", "contents", False)],
        )
        result = await transcript_service.render_json(db_session, session_model.id)
        entry = result["entries"][0]
        assert entry["type"] == "tool_call"
        assert entry["tool_name"] == "read_file"
        assert "input-c1" in entry["input"]
        assert entry["output"] == "contents"
        assert entry["is_error"] is False


# ---------------------------------------------------------------------------
# Integration tests: REST transcript endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTranscriptRESTEndpoint:
    async def test_default_format_json(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET /api/sessions/{id}/transcript returns JSON transcript by default."""
        from tests.conftest import ensure_workspace_membership

        project = await db_session.get(Project, session_model.project_id)
        await ensure_workspace_membership(db_session, project.workspace_id)

        resp = await client.get(f"/api/sessions/{session_model.id}/transcript")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == str(session_model.id)
        assert data["session_name"] == "test-session"
        assert data["entry_count"] == 0
        assert data["entries"] == []

    async def test_format_json_explicit(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET /api/sessions/{id}/transcript?format=json returns TranscriptExportJSON schema."""
        from tests.conftest import ensure_workspace_membership

        project = await db_session.get(Project, session_model.project_id)
        await ensure_workspace_membership(db_session, project.workspace_id)

        await _seed_messages(db_session, session_model.id, [("user", "Hi")])
        resp = await client.get(f"/api/sessions/{session_model.id}/transcript?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entry_count"] == 1
        assert data["entries"][0]["type"] == "message"

    async def test_format_markdown(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET /api/sessions/{id}/transcript?format=markdown returns text/markdown."""
        from tests.conftest import ensure_workspace_membership

        project = await db_session.get(Project, session_model.project_id)
        await ensure_workspace_membership(db_session, project.workspace_id)

        resp = await client.get(f"/api/sessions/{session_model.id}/transcript?format=markdown")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
        assert "# Session: test-session" in resp.text

    async def test_markdown_content_disposition(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET /api/sessions/{id}/transcript?format=markdown includes Content-Disposition header."""
        from tests.conftest import ensure_workspace_membership

        project = await db_session.get(Project, session_model.project_id)
        await ensure_workspace_membership(db_session, project.workspace_id)

        resp = await client.get(f"/api/sessions/{session_model.id}/transcript?format=markdown")
        assert resp.status_code == 200
        assert "content-disposition" in resp.headers
        assert "session-test-session.md" in resp.headers["content-disposition"]

    async def test_invalid_format_400(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """GET /api/sessions/{id}/transcript?format=invalid returns 400."""
        from tests.conftest import ensure_workspace_membership

        project = await db_session.get(Project, session_model.project_id)
        await ensure_workspace_membership(db_session, project.workspace_id)

        resp = await client.get(f"/api/sessions/{session_model.id}/transcript?format=invalid")
        assert resp.status_code == 400

    async def test_nonexistent_session_404(self, client: AsyncClient):
        """GET /api/sessions/{id}/transcript for non-existent session returns 404."""
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/transcript")
        assert resp.status_code == 404

    async def test_viewer_access_required(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_model: SessionModel,
    ):
        """Transcript endpoint enforces viewer-level access (403 for unauthorized user)."""
        # Don't set up workspace membership -- should get 403
        resp = await client.get(f"/api/sessions/{session_model.id}/transcript")
        assert resp.status_code == 403
