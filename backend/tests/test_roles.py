"""Tests for the agent roles system: loading, validation, merging, API, engine integration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
import yaml

from codehive.db.models import Base
from codehive.core.roles import (
    RoleDefinition,
    RoleNotFoundError,
    build_role_system_prompt,
    filter_tools_for_role,
    list_builtin_roles,
    load_role,
    merge_role,
    reset_builtin_dir,
    set_builtin_dir,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_builtin_dir():
    """Ensure the builtin dir is reset after each test."""
    yield
    reset_builtin_dir()


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
# Unit: Role Loading and Validation
# ---------------------------------------------------------------------------


class TestRoleLoading:
    def test_load_all_builtin_roles(self):
        """Load each of the 6 built-in roles from YAML, verify all fields parse."""
        expected = {
            "developer",
            "tester",
            "product_manager",
            "research_agent",
            "bug_fixer",
            "refactor_engineer",
        }
        names = set(list_builtin_roles())
        assert names == expected

        for name in expected:
            role = load_role(name)
            assert isinstance(role, RoleDefinition)
            assert role.name == name
            assert role.display_name  # non-empty
            assert role.description  # non-empty

    def test_load_developer_role_fields(self):
        """Developer role has expected tools and coding rules."""
        role = load_role("developer")
        assert "edit_file" in role.allowed_tools
        assert "read_file" in role.allowed_tools
        assert "use type hints" in role.coding_rules
        assert role.system_prompt_extra.strip()

    def test_load_role_with_defaults(self, tmp_path: Path):
        """Load a role with missing optional fields, verify defaults apply."""
        set_builtin_dir(tmp_path)
        (tmp_path / "minimal.yaml").write_text(yaml.dump({"name": "minimal"}))

        role = load_role("minimal")
        assert role.name == "minimal"
        assert role.display_name == ""
        assert role.description == ""
        assert role.responsibilities == []
        assert role.allowed_tools == []
        assert role.denied_tools == []
        assert role.coding_rules == []
        assert role.system_prompt_extra == ""

    def test_load_nonexistent_role_raises(self):
        """Attempt to load a nonexistent role raises RoleNotFoundError."""
        with pytest.raises(RoleNotFoundError, match="not found"):
            load_role("nonexistent_role_xyz")

    def test_empty_name_rejected(self):
        """A role with an empty name field is rejected."""
        with pytest.raises(Exception):
            RoleDefinition(name="")

    def test_whitespace_name_rejected(self):
        """A role with a whitespace-only name is rejected."""
        with pytest.raises(Exception):
            RoleDefinition(name="   ")

    def test_invalid_yaml_structure_rejected(self, tmp_path: Path):
        """YAML with invalid structure (allowed_tools is a string) is rejected."""
        set_builtin_dir(tmp_path)
        (tmp_path / "bad.yaml").write_text(
            yaml.dump({"name": "bad", "allowed_tools": "not_a_list"})
        )
        with pytest.raises(Exception):
            load_role("bad")

    def test_list_builtin_roles(self):
        """list_builtin_roles returns names of all built-in YAML role files."""
        names = list_builtin_roles()
        assert len(names) == 6
        assert "developer" in names
        assert "tester" in names

    def test_load_role_from_custom_dict(self, tmp_path: Path):
        """load_role falls back to custom_roles dict when not found as built-in."""
        set_builtin_dir(tmp_path)  # empty dir, no built-in roles
        custom = {
            "my_role": {"name": "my_role", "display_name": "My Role", "description": "custom"},
        }
        role = load_role("my_role", custom_roles=custom)
        assert role.name == "my_role"
        assert role.display_name == "My Role"


# ---------------------------------------------------------------------------
# Unit: Role Merging
# ---------------------------------------------------------------------------


class TestRoleMerging:
    def test_merge_with_empty_overrides(self):
        """Merge a global role with empty overrides preserves global values."""
        role = load_role("developer")
        merged = merge_role(role, {})
        assert merged.name == role.name
        assert merged.allowed_tools == role.allowed_tools
        assert merged.coding_rules == role.coding_rules

    def test_merge_replaces_allowed_tools(self):
        """Override allowed_tools replaces (not appends) the global list."""
        role = load_role("developer")
        original_tools = role.allowed_tools.copy()
        assert len(original_tools) > 1

        merged = merge_role(role, {"allowed_tools": ["read_file"]})
        assert merged.allowed_tools == ["read_file"]
        # Original is unchanged
        assert role.allowed_tools == original_tools

    def test_merge_replaces_coding_rules_and_prompt(self):
        """Override coding_rules and system_prompt_extra replaces both."""
        role = load_role("developer")
        merged = merge_role(
            role,
            {
                "coding_rules": ["custom rule"],
                "system_prompt_extra": "Custom prompt",
            },
        )
        assert merged.coding_rules == ["custom rule"]
        assert merged.system_prompt_extra == "Custom prompt"

    def test_merge_partial_override_preserves_others(self):
        """Partial override (only description) preserves other fields."""
        role = load_role("developer")
        merged = merge_role(role, {"description": "Overridden description"})
        assert merged.description == "Overridden description"
        assert merged.allowed_tools == role.allowed_tools
        assert merged.coding_rules == role.coding_rules
        assert merged.system_prompt_extra == role.system_prompt_extra


# ---------------------------------------------------------------------------
# Unit: Tool Filtering from Role
# ---------------------------------------------------------------------------


class TestToolFiltering:
    def test_filter_by_allowed_tools(self):
        """Role with allowed_tools keeps only those tools."""
        role = RoleDefinition(
            name="test",
            allowed_tools=["read_file", "search_files"],
        )
        filtered = filter_tools_for_role(SAMPLE_TOOL_DEFINITIONS, role)
        names = [t["name"] for t in filtered]
        assert set(names) == {"read_file", "search_files"}

    def test_filter_by_denied_tools(self):
        """Role with denied_tools removes those and keeps all others."""
        role = RoleDefinition(
            name="test",
            denied_tools=["git_commit"],
        )
        filtered = filter_tools_for_role(SAMPLE_TOOL_DEFINITIONS, role)
        names = [t["name"] for t in filtered]
        assert "git_commit" not in names
        assert len(names) == len(SAMPLE_TOOL_DEFINITIONS) - 1

    def test_denied_takes_priority_over_allowed(self):
        """When both allowed and denied are set, denied takes priority."""
        role = RoleDefinition(
            name="test",
            allowed_tools=["read_file", "git_commit"],
            denied_tools=["git_commit"],
        )
        filtered = filter_tools_for_role(SAMPLE_TOOL_DEFINITIONS, role)
        names = [t["name"] for t in filtered]
        assert names == ["read_file"]

    def test_empty_allowed_tools_keeps_all(self):
        """Role with no allowed_tools set returns all tools."""
        role = RoleDefinition(name="test")
        filtered = filter_tools_for_role(SAMPLE_TOOL_DEFINITIONS, role)
        assert len(filtered) == len(SAMPLE_TOOL_DEFINITIONS)


# ---------------------------------------------------------------------------
# Unit: System Prompt Construction from Role
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    def test_prompt_with_extra_and_rules(self):
        """Role with system_prompt_extra and coding_rules produces both in prompt."""
        role = RoleDefinition(
            name="test",
            system_prompt_extra="Be careful.",
            coding_rules=["use type hints", "write tests"],
        )
        prompt = build_role_system_prompt(role)
        assert "Be careful." in prompt
        assert "Coding rules:" in prompt
        assert "1. use type hints" in prompt
        assert "2. write tests" in prompt

    def test_prompt_with_no_extra(self):
        """Role with no system_prompt_extra returns only coding rules or empty."""
        role = RoleDefinition(name="test")
        prompt = build_role_system_prompt(role)
        assert prompt == ""

    def test_prompt_rules_formatted_as_numbered_list(self):
        """Coding rules are formatted as a numbered list."""
        role = RoleDefinition(
            name="test",
            coding_rules=["rule A", "rule B", "rule C"],
        )
        prompt = build_role_system_prompt(role)
        assert "1. rule A" in prompt
        assert "2. rule B" in prompt
        assert "3. rule C" in prompt


# ---------------------------------------------------------------------------
# Integration: API Endpoints
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


class TestRolesAPI:
    @pytest.mark.asyncio
    async def test_list_roles_includes_builtins(self, async_client):
        """GET /api/roles returns list including all 6 built-in roles."""
        resp = await async_client.get("/api/roles")
        assert resp.status_code == 200
        data = resp.json()
        names = [r["name"] for r in data]
        assert "developer" in names
        assert "tester" in names
        assert "product_manager" in names
        assert len([r for r in data if r["is_builtin"]]) == 6

    @pytest.mark.asyncio
    async def test_get_builtin_role(self, async_client):
        """GET /api/roles/developer returns the developer role."""
        resp = await async_client.get("/api/roles/developer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "developer"
        assert data["is_builtin"] is True
        assert "edit_file" in data["allowed_tools"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_role(self, async_client):
        """GET /api/roles/nonexistent returns 404."""
        resp = await async_client.get("/api/roles/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_custom_role(self, async_client):
        """POST /api/roles with valid body creates a custom role, returns 201."""
        body = {
            "name": "security_auditor",
            "display_name": "Security Auditor",
            "description": "Reviews code for security issues",
            "allowed_tools": ["read_file", "search_files"],
        }
        resp = await async_client.post("/api/roles", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "security_auditor"
        assert data["is_builtin"] is False
        assert data["allowed_tools"] == ["read_file", "search_files"]

    @pytest.mark.asyncio
    async def test_create_duplicate_role_409(self, async_client):
        """POST /api/roles with duplicate name returns 409."""
        body = {"name": "dup_role", "display_name": "Dup"}
        resp = await async_client.post("/api/roles", json=body)
        assert resp.status_code == 201

        resp2 = await async_client.post("/api/roles", json=body)
        assert resp2.status_code == 409

    @pytest.mark.asyncio
    async def test_create_role_with_builtin_name_409(self, async_client):
        """POST /api/roles with a built-in name returns 409."""
        body = {"name": "developer", "display_name": "My Developer"}
        resp = await async_client.post("/api/roles", json=body)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_update_custom_role(self, async_client):
        """PUT /api/roles/my_custom_role updates the custom role."""
        create_body = {"name": "updatable", "display_name": "V1", "description": "Original"}
        resp = await async_client.post("/api/roles", json=create_body)
        assert resp.status_code == 201

        update_body = {"display_name": "V2", "description": "Updated"}
        resp2 = await async_client.put("/api/roles/updatable", json=update_body)
        assert resp2.status_code == 200
        assert resp2.json()["display_name"] == "V2"
        assert resp2.json()["description"] == "Updated"

    @pytest.mark.asyncio
    async def test_update_builtin_role_403(self, async_client):
        """PUT /api/roles/developer returns 403 (cannot modify built-in)."""
        resp = await async_client.put(
            "/api/roles/developer",
            json={"display_name": "Hacked"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_custom_role(self, async_client):
        """DELETE /api/roles/my_custom_role returns 204."""
        body = {"name": "deletable", "display_name": "Delete Me"}
        resp = await async_client.post("/api/roles", json=body)
        assert resp.status_code == 201

        resp2 = await async_client.delete("/api/roles/deletable")
        assert resp2.status_code == 204

        # Verify it's gone
        resp3 = await async_client.get("/api/roles/deletable")
        assert resp3.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_builtin_role_403(self, async_client):
        """DELETE /api/roles/developer returns 403 (cannot delete built-in)."""
        resp = await async_client.delete("/api/roles/developer")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_roles_includes_custom(self, async_client):
        """GET /api/roles after creating a custom role includes it alongside built-ins."""
        body = {"name": "custom_listed", "display_name": "Custom Listed"}
        await async_client.post("/api/roles", json=body)

        resp = await async_client.get("/api/roles")
        names = [r["name"] for r in resp.json()]
        assert "custom_listed" in names
        assert "developer" in names


# ---------------------------------------------------------------------------
# Integration: Engine with Roles
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
    """Create a ZaiEngine with mocked dependencies."""
    from codehive.engine import ZaiEngine
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

    engine = ZaiEngine(
        client=client,
        event_bus=event_bus,
        file_ops=file_ops,
        shell_runner=shell_runner,
        git_ops=git_ops,
        diff_service=diff_service,
    )

    return engine, {"client": client, "event_bus": event_bus}


class _MockStream:
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


class TestEngineRoleIntegration:
    @pytest.mark.asyncio
    async def test_role_filters_tools(self, tmp_path: Path):
        """Session with role='tester' only sends tester-allowed tools to API."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(mocks, MockResponse(content=[MockTextBlock(text="Done.")]))

        await _collect_events(engine.send_message(session_id, "Test something", role="tester"))

        # Check that tools were filtered to tester's allowed_tools
        call_kwargs = mocks["client"].messages.stream.call_args
        tool_names = [t["name"] for t in call_kwargs.kwargs["tools"]]
        # Tester allows: read_file, run_shell, search_files
        # Tester denies: git_commit
        assert "read_file" in tool_names
        assert "run_shell" in tool_names
        assert "search_files" in tool_names
        assert "edit_file" not in tool_names
        assert "git_commit" not in tool_names

    @pytest.mark.asyncio
    async def test_orchestrator_and_role_intersection(self, tmp_path: Path):
        """Orchestrator mode + role: tools are the intersection."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(mocks, MockResponse(content=[MockTextBlock(text="Done.")]))

        # Developer role allows: edit_file, read_file, run_shell, git_commit, search_files
        # Orchestrator allows: spawn_subagent, read_file, search_files, run_shell
        # Intersection: read_file, run_shell, search_files
        await _collect_events(
            engine.send_message(session_id, "Plan work", mode="orchestrator", role="developer")
        )

        call_kwargs = mocks["client"].messages.stream.call_args
        tool_names = set(t["name"] for t in call_kwargs.kwargs["tools"])
        assert tool_names == {"read_file", "search_files", "run_shell"}

    @pytest.mark.asyncio
    async def test_role_system_prompt_included(self, tmp_path: Path):
        """System prompt includes role-specific content when a role is set."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(mocks, MockResponse(content=[MockTextBlock(text="Done.")]))

        await _collect_events(engine.send_message(session_id, "Hello", role="developer"))

        call_kwargs = mocks["client"].messages.stream.call_args
        system = call_kwargs.kwargs.get("system", "")
        assert "developer agent" in system.lower()
        assert "type hints" in system.lower()

    @pytest.mark.asyncio
    async def test_role_definition_object_accepted(self, tmp_path: Path):
        """send_message accepts a RoleDefinition object directly."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(mocks, MockResponse(content=[MockTextBlock(text="Done.")]))

        custom_role = RoleDefinition(
            name="custom",
            allowed_tools=["read_file"],
            system_prompt_extra="Custom agent prompt.",
        )

        await _collect_events(engine.send_message(session_id, "Hi", role=custom_role))

        call_kwargs = mocks["client"].messages.stream.call_args
        tool_names = [t["name"] for t in call_kwargs.kwargs["tools"]]
        assert tool_names == ["read_file"]
        assert "Custom agent prompt." in call_kwargs.kwargs.get("system", "")

    @pytest.mark.asyncio
    async def test_no_role_no_system_prompt(self, tmp_path: Path):
        """Without a role or orchestrator mode, no system prompt is set."""
        engine, mocks = _make_engine(tmp_path)
        session_id = uuid.uuid4()
        await engine.create_session(session_id)

        _setup_stream_mock(mocks, MockResponse(content=[MockTextBlock(text="Done.")]))

        await _collect_events(engine.send_message(session_id, "Hi"))

        call_kwargs = mocks["client"].messages.stream.call_args
        assert "system" not in call_kwargs.kwargs
