"""Tests for the agent modes system: definitions, tool filtering, engine integration, API."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from codehive.db.models import Base
from codehive.core.modes import (
    MODES,
    VALID_MODES,
    ModeDefinition,
    ModeNotFoundError,
    build_mode_system_prompt,
    filter_tools_for_mode,
    get_mode,
)


# ---------------------------------------------------------------------------
# Shared tool definitions for testing
# ---------------------------------------------------------------------------

SAMPLE_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read a file",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "edit_file",
        "description": "Edit a file",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_shell",
        "description": "Run shell",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "git_commit",
        "description": "Git commit",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_files",
        "description": "Search files",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "spawn_subagent",
        "description": "Spawn sub-agent",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


# ---------------------------------------------------------------------------
# Unit: Mode Definitions
# ---------------------------------------------------------------------------


class TestModeDefinitions:
    def test_valid_modes_set(self):
        """VALID_MODES contains exactly the 5 expected modes."""
        assert VALID_MODES == {"brainstorm", "interview", "planning", "execution", "review"}

    def test_load_each_mode_by_name(self):
        """Load each of the 5 modes by name, verify system_prompt is non-empty."""
        for name in VALID_MODES:
            mode = get_mode(name)
            assert isinstance(mode, ModeDefinition)
            assert mode.name == name
            assert mode.system_prompt  # non-empty

    def test_get_mode_invalid_raises(self):
        """get_mode with invalid name raises ModeNotFoundError."""
        with pytest.raises(ModeNotFoundError, match="not found"):
            get_mode("nonexistent")

    def test_modes_dict_has_all_entries(self):
        """MODES dict has entries for all 5 modes."""
        assert set(MODES.keys()) == VALID_MODES


# ---------------------------------------------------------------------------
# Unit: Tool Filtering
# ---------------------------------------------------------------------------


class TestModeToolFiltering:
    def test_brainstorm_allows_only_read_and_search(self):
        """filter_tools_for_mode with brainstorm returns only read_file and search_files."""
        mode = get_mode("brainstorm")
        filtered = filter_tools_for_mode(SAMPLE_TOOL_DEFINITIONS, mode)
        names = {t["name"] for t in filtered}
        assert names == {"read_file", "search_files"}

    def test_interview_allows_only_read_and_search(self):
        """filter_tools_for_mode with interview returns only read_file and search_files."""
        mode = get_mode("interview")
        filtered = filter_tools_for_mode(SAMPLE_TOOL_DEFINITIONS, mode)
        names = {t["name"] for t in filtered}
        assert names == {"read_file", "search_files"}

    def test_execution_allows_all_tools(self):
        """filter_tools_for_mode with execution returns all tools."""
        mode = get_mode("execution")
        filtered = filter_tools_for_mode(SAMPLE_TOOL_DEFINITIONS, mode)
        assert len(filtered) == len(SAMPLE_TOOL_DEFINITIONS)

    def test_review_excludes_edit_git_spawn(self):
        """filter_tools_for_mode with review excludes edit_file, git_commit, spawn_subagent."""
        mode = get_mode("review")
        filtered = filter_tools_for_mode(SAMPLE_TOOL_DEFINITIONS, mode)
        names = {t["name"] for t in filtered}
        assert "edit_file" not in names
        assert "git_commit" not in names
        assert "spawn_subagent" not in names
        assert "read_file" in names
        assert "search_files" in names
        assert "run_shell" in names

    def test_planning_excludes_edit_and_git(self):
        """filter_tools_for_mode with planning excludes edit_file and git_commit but allows run_shell."""
        mode = get_mode("planning")
        filtered = filter_tools_for_mode(SAMPLE_TOOL_DEFINITIONS, mode)
        names = {t["name"] for t in filtered}
        assert "edit_file" not in names
        assert "git_commit" not in names
        assert "run_shell" in names
        assert "read_file" in names
        assert "search_files" in names


# ---------------------------------------------------------------------------
# Unit: System Prompt
# ---------------------------------------------------------------------------


class TestModeSystemPrompt:
    def test_build_mode_system_prompt_non_empty(self):
        """build_mode_system_prompt returns non-empty string for each mode."""
        for name in VALID_MODES:
            mode = get_mode(name)
            prompt = build_mode_system_prompt(mode)
            assert isinstance(prompt, str)
            assert len(prompt) > 0


# ---------------------------------------------------------------------------
# Unit: Engine Mode Integration
# ---------------------------------------------------------------------------


@dataclass
class MockTextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class MockToolUseBlock:
    type: str = "tool_use"
    id: str = "tool_1"
    name: str = "read_file"
    input: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.input is None:
            self.input = {}


@dataclass
class MockResponse:
    content: list = None  # type: ignore[assignment]
    stop_reason: str = "end_turn"

    def __post_init__(self) -> None:
        if self.content is None:
            self.content = []


def _make_engine(tmp_path: Path):
    """Create a NativeEngine with mocked dependencies."""
    from codehive.engine import NativeEngine
    from codehive.execution.diff import DiffService
    from codehive.execution.file_ops import FileOps
    from codehive.execution.git_ops import GitOps
    from codehive.execution.shell import ShellRunner

    client = AsyncMock()
    event_bus = AsyncMock()
    file_ops = FileOps(tmp_path)
    shell_runner = ShellRunner()
    git_ops = GitOps(tmp_path)
    diff_service = DiffService()

    engine = NativeEngine(
        client=client,
        event_bus=event_bus,
        file_ops=file_ops,
        shell_runner=shell_runner,
        git_ops=git_ops,
        diff_service=diff_service,
    )

    return engine, {"client": client, "event_bus": event_bus}


class _MockStream:
    """Mock for the Anthropic streaming context manager."""

    def __init__(self, response: MockResponse) -> None:
        self._response = response
        self._text_chunks: list[str] = []
        for block in response.content:
            if block.type == "text":
                self._text_chunks.append(block.text)

    async def __aenter__(self) -> _MockStream:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    @property
    def text_stream(self) -> _TextStreamIter:
        return _TextStreamIter(self._text_chunks)

    async def get_final_message(self) -> MockResponse:
        return self._response


class _TextStreamIter:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks
        self._index = 0

    def __aiter__(self) -> _TextStreamIter:
        return self

    async def __anext__(self) -> str:
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


def _setup_stream_mock(mocks: dict[str, Any], responses: list[MockResponse] | MockResponse) -> None:
    if isinstance(responses, MockResponse):
        responses = [responses]
    call_count = 0

    def stream_side_effect(**kwargs: Any) -> _MockStream:
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return _MockStream(responses[idx])

    mocks["client"].messages.stream = MagicMock(side_effect=stream_side_effect)


async def _collect_events(aiter: Any) -> list[dict]:
    events = []
    async for event in aiter:
        events.append(event)
    return events


class TestEngineModeIntegration:
    @pytest.mark.asyncio
    async def test_brainstorm_rejects_edit_file(self, tmp_path: Path):
        """send_message with mode='brainstorm' rejects an edit_file tool call with error."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            [
                MockResponse(
                    content=[
                        MockToolUseBlock(
                            id="tool_1",
                            name="edit_file",
                            input={"path": "test.txt", "old_text": "a", "new_text": "b"},
                        )
                    ]
                ),
                MockResponse(content=[MockTextBlock(text="OK.")]),
            ],
        )

        events = await _collect_events(
            engine.send_message(session_id, "Edit something", mode="brainstorm")
        )

        # The edit_file call should be rejected
        finished = [e for e in events if e["type"] == "tool.call.finished"]
        assert len(finished) == 1
        assert finished[0]["result"]["is_error"] is True
        assert "brainstorm" in finished[0]["result"]["content"]

    @pytest.mark.asyncio
    async def test_execution_allows_all_tools(self, tmp_path: Path):
        """send_message with mode='execution' allows all tool calls."""
        (tmp_path / "test.txt").write_text("hello")
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(
            mocks,
            [
                MockResponse(
                    content=[
                        MockToolUseBlock(
                            id="tool_1",
                            name="read_file",
                            input={"path": "test.txt"},
                        )
                    ]
                ),
                MockResponse(content=[MockTextBlock(text="Done.")]),
            ],
        )

        events = await _collect_events(
            engine.send_message(session_id, "Read file", mode="execution")
        )

        finished = [e for e in events if e["type"] == "tool.call.finished"]
        assert len(finished) == 1
        assert "is_error" not in finished[0]["result"]

    @pytest.mark.asyncio
    async def test_mode_system_prompt_in_api_call(self, tmp_path: Path):
        """Mode system prompt appears in the API call's system parameter."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(mocks, MockResponse(content=[MockTextBlock(text="Done.")]))

        await _collect_events(engine.send_message(session_id, "Hello", mode="brainstorm"))

        call_kwargs = mocks["client"].messages.stream.call_args
        system = call_kwargs.kwargs.get("system", "")
        assert "brainstorm" in system.lower()

    @pytest.mark.asyncio
    async def test_mode_and_role_tool_intersection(self, tmp_path: Path):
        """When both mode and role are set, tool set is the intersection."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(mocks, MockResponse(content=[MockTextBlock(text="Done.")]))

        # Planning mode allows: read_file, search_files, run_shell
        # Developer role allows: edit_file, read_file, run_shell, git_commit, search_files
        # Intersection: read_file, search_files, run_shell
        await _collect_events(
            engine.send_message(session_id, "Plan work", mode="planning", role="developer")
        )

        call_kwargs = mocks["client"].messages.stream.call_args
        tool_names = {t["name"] for t in call_kwargs.kwargs["tools"]}
        assert tool_names == {"read_file", "search_files", "run_shell"}

    @pytest.mark.asyncio
    async def test_mode_tools_filtered_in_api_call(self, tmp_path: Path):
        """Brainstorm mode only sends allowed tools to the API."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(mocks, MockResponse(content=[MockTextBlock(text="Done.")]))

        await _collect_events(engine.send_message(session_id, "Think", mode="brainstorm"))

        call_kwargs = mocks["client"].messages.stream.call_args
        tool_names = {t["name"] for t in call_kwargs.kwargs["tools"]}
        assert tool_names == {"read_file", "search_files"}


# ---------------------------------------------------------------------------
# Integration: API Mode Switching
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """Create tables in an in-memory SQLite DB and yield an async session."""
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
async def async_client(db_session):
    """Create an async test client with the DB session overridden."""
    from collections.abc import AsyncGenerator

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from codehive.api.app import create_app
    from codehive.api.deps import get_db

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


async def _create_project(db_session) -> str:
    """Helper to create a project in DB and return its ID as string."""
    from codehive.db.models import Workspace, Project
    from datetime import datetime, timezone
    from tests.conftest import ensure_workspace_membership

    ws = Workspace(
        name="test-ws", root_path="/tmp/test-ws", settings={}, created_at=datetime.now(timezone.utc)
    )
    db_session.add(ws)
    await db_session.flush()

    proj = Project(
        workspace_id=ws.id,
        name="test-proj",
        path="/tmp/test",
        knowledge={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)

    await ensure_workspace_membership(db_session, ws.id)

    return str(proj.id)


class TestAPIModeSwitch:
    @pytest.mark.asyncio
    async def test_switch_mode_success(self, async_client, db_session):
        """POST /api/sessions/{id}/switch-mode with valid mode updates DB."""
        project_id = await _create_project(db_session)

        # Create session with execution mode
        resp = await async_client.post(
            f"/api/projects/{project_id}/sessions",
            json={"name": "test", "engine": "native", "mode": "execution"},
        )
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        # Switch to review mode
        resp = await async_client.post(
            f"/api/sessions/{session_id}/switch-mode",
            json={"mode": "review"},
        )
        assert resp.status_code == 200
        assert resp.json()["mode"] == "review"

    @pytest.mark.asyncio
    async def test_switch_mode_invalid_returns_422(self, async_client, db_session):
        """POST /api/sessions/{id}/switch-mode with invalid mode returns 422."""
        project_id = await _create_project(db_session)

        resp = await async_client.post(
            f"/api/projects/{project_id}/sessions",
            json={"name": "test", "engine": "native", "mode": "execution"},
        )
        session_id = resp.json()["id"]

        resp = await async_client.post(
            f"/api/sessions/{session_id}/switch-mode",
            json={"mode": "invalid_mode"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_switch_mode_nonexistent_session_returns_404(self, async_client):
        """POST /api/sessions/{id}/switch-mode with nonexistent session returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await async_client.post(
            f"/api/sessions/{fake_id}/switch-mode",
            json={"mode": "review"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_session_with_invalid_mode_returns_422(self, async_client, db_session):
        """Creating a session with invalid mode returns validation error."""
        project_id = await _create_project(db_session)

        resp = await async_client.post(
            f"/api/projects/{project_id}/sessions",
            json={"name": "test", "engine": "native", "mode": "invalid_mode"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_session_with_valid_mode_succeeds(self, async_client, db_session):
        """Creating a session with mode='brainstorm' succeeds."""
        project_id = await _create_project(db_session)

        resp = await async_client.post(
            f"/api/projects/{project_id}/sessions",
            json={"name": "test", "engine": "native", "mode": "brainstorm"},
        )
        assert resp.status_code == 201
        assert resp.json()["mode"] == "brainstorm"

    @pytest.mark.asyncio
    async def test_create_session_with_orchestrator_mode_succeeds(self, async_client, db_session):
        """Creating a session with mode='orchestrator' succeeds."""
        project_id = await _create_project(db_session)

        resp = await async_client.post(
            f"/api/projects/{project_id}/sessions",
            json={"name": "test", "engine": "native", "mode": "orchestrator"},
        )
        assert resp.status_code == 201
        assert resp.json()["mode"] == "orchestrator"
