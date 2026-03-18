"""Tests for project knowledge base and agent charter (issue #48)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.knowledge import (
    build_knowledge_context,
    get_charter,
    get_knowledge,
    set_charter,
    update_knowledge,
)
from codehive.core.project import ProjectNotFoundError, create_project
from codehive.db.models import Base, Project, Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database
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
async def project(db_session: AsyncSession) -> Project:
    return await create_project(
        db_session,
        name="test-project",
    )


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
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


# ---------------------------------------------------------------------------
# Unit tests: Core knowledge CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreKnowledgeGet:
    async def test_get_empty_knowledge(self, db_session: AsyncSession, project: Project):
        knowledge = await get_knowledge(db_session, project.id)
        assert knowledge == {}

    async def test_get_knowledge_with_archetype_data(
        self, db_session: AsyncSession, project: Project
    ):
        # Manually set archetype data
        project.knowledge = {
            "archetype_roles": ["developer"],
            "archetype_settings": {"workflow": "agile"},
        }
        await db_session.commit()
        await db_session.refresh(project)

        knowledge = await get_knowledge(db_session, project.id)
        assert "archetype_roles" in knowledge
        assert knowledge["archetype_roles"] == ["developer"]

    async def test_get_knowledge_nonexistent_project(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await get_knowledge(db_session, uuid.uuid4())


@pytest.mark.asyncio
class TestCoreKnowledgeUpdate:
    async def test_update_with_tech_stack(self, db_session: AsyncSession, project: Project):
        result = await update_knowledge(
            db_session, project.id, {"tech_stack": {"language": "python"}}
        )
        assert result["tech_stack"] == {"language": "python"}

    async def test_update_twice_different_sections(
        self, db_session: AsyncSession, project: Project
    ):
        await update_knowledge(db_session, project.id, {"tech_stack": {"language": "python"}})
        result = await update_knowledge(db_session, project.id, {"conventions": {"style": "black"}})
        assert result["tech_stack"] == {"language": "python"}
        assert result["conventions"] == {"style": "black"}

    async def test_update_existing_section_overwrites(
        self, db_session: AsyncSession, project: Project
    ):
        await update_knowledge(db_session, project.id, {"tech_stack": {"language": "python"}})
        result = await update_knowledge(
            db_session, project.id, {"tech_stack": {"language": "rust"}}
        )
        assert result["tech_stack"] == {"language": "rust"}

    async def test_archetype_keys_survive_update(self, db_session: AsyncSession, project: Project):
        # Pre-set archetype data
        project.knowledge = {
            "archetype_roles": ["developer", "tester"],
            "archetype_settings": {"auto_test": True},
        }
        await db_session.commit()
        await db_session.refresh(project)

        result = await update_knowledge(
            db_session, project.id, {"tech_stack": {"language": "python"}}
        )
        assert result["archetype_roles"] == ["developer", "tester"]
        assert result["archetype_settings"] == {"auto_test": True}
        assert result["tech_stack"] == {"language": "python"}

    async def test_update_nonexistent_project(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await update_knowledge(db_session, uuid.uuid4(), {"tech_stack": {}})


@pytest.mark.asyncio
class TestCoreCharter:
    async def test_get_charter_when_none(self, db_session: AsyncSession, project: Project):
        charter = await get_charter(db_session, project.id)
        assert charter == {}

    async def test_set_then_get_charter(self, db_session: AsyncSession, project: Project):
        charter_data = {
            "goals": ["Ship MVP"],
            "constraints": ["No external API calls"],
            "tech_stack_rules": [],
            "coding_rules": ["Type hints required"],
            "decision_policies": [],
        }
        saved = await set_charter(db_session, project.id, charter_data)
        assert saved["goals"] == ["Ship MVP"]

        retrieved = await get_charter(db_session, project.id)
        assert retrieved["goals"] == ["Ship MVP"]
        assert retrieved["constraints"] == ["No external API calls"]

    async def test_replace_charter(self, db_session: AsyncSession, project: Project):
        await set_charter(db_session, project.id, {"goals": ["old goal"]})
        replaced = await set_charter(db_session, project.id, {"goals": ["new goal"]})
        assert replaced["goals"] == ["new goal"]
        # Old content is fully replaced
        retrieved = await get_charter(db_session, project.id)
        assert retrieved["goals"] == ["new goal"]

    async def test_charter_nonexistent_project(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await get_charter(db_session, uuid.uuid4())

        with pytest.raises(ProjectNotFoundError):
            await set_charter(db_session, uuid.uuid4(), {"goals": []})


# ---------------------------------------------------------------------------
# Integration tests: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestKnowledgeAPI:
    async def test_get_knowledge_fresh_project(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/projects",
            json={"name": "kb-project"},
        )
        project_id = create_resp.json()["id"]

        resp = await client.get(f"/api/projects/{project_id}/knowledge")
        assert resp.status_code == 200
        assert resp.json() == {}

    async def test_patch_knowledge_tech_stack(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/projects",
            json={"name": "kb-patch"},
        )
        project_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/projects/{project_id}/knowledge",
            json={"tech_stack": {"language": "python"}},
        )
        assert resp.status_code == 200
        assert resp.json()["tech_stack"] == {"language": "python"}

    async def test_patch_knowledge_merge(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/projects",
            json={"name": "kb-merge"},
        )
        project_id = create_resp.json()["id"]

        await client.patch(
            f"/api/projects/{project_id}/knowledge",
            json={"tech_stack": {"language": "python"}},
        )
        resp = await client.patch(
            f"/api/projects/{project_id}/knowledge",
            json={"conventions": {"style": "black"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tech_stack"] == {"language": "python"}
        assert data["conventions"] == {"style": "black"}

    async def test_patch_knowledge_invalid_structure(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/projects",
            json={"name": "kb-invalid"},
        )
        project_id = create_resp.json()["id"]

        # tech_stack expects dict, send a string
        resp = await client.patch(
            f"/api/projects/{project_id}/knowledge",
            json={"tech_stack": "not-a-dict"},
        )
        assert resp.status_code == 422

    async def test_knowledge_404_nonexistent_project(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/projects/{fake_id}/knowledge")
        assert resp.status_code == 404

        resp = await client.patch(
            f"/api/projects/{fake_id}/knowledge",
            json={"tech_stack": {"language": "python"}},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestCharterAPI:
    async def test_get_charter_fresh_project(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/projects",
            json={"name": "charter-fresh"},
        )
        project_id = create_resp.json()["id"]

        resp = await client.get(f"/api/projects/{project_id}/charter")
        assert resp.status_code == 200
        assert resp.json() == {}

    async def test_put_charter(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/projects",
            json={"name": "charter-put"},
        )
        project_id = create_resp.json()["id"]

        charter = {
            "goals": ["Ship MVP by Q2"],
            "constraints": ["No external API calls in tests"],
            "tech_stack_rules": ["Python 3.12+"],
            "coding_rules": ["Type hints required"],
            "decision_policies": ["Prefer simplicity"],
        }
        resp = await client.put(
            f"/api/projects/{project_id}/charter",
            json=charter,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["goals"] == ["Ship MVP by Q2"]

    async def test_get_charter_after_put(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/projects",
            json={"name": "charter-persist"},
        )
        project_id = create_resp.json()["id"]

        charter = {
            "goals": ["Goal A"],
            "constraints": [],
            "tech_stack_rules": [],
            "coding_rules": [],
            "decision_policies": [],
        }
        await client.put(f"/api/projects/{project_id}/charter", json=charter)

        resp = await client.get(f"/api/projects/{project_id}/charter")
        assert resp.status_code == 200
        assert resp.json()["goals"] == ["Goal A"]

    async def test_charter_404_nonexistent_project(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/projects/{fake_id}/charter")
        assert resp.status_code == 404

        resp = await client.put(
            f"/api/projects/{fake_id}/charter",
            json={
                "goals": [],
                "constraints": [],
                "tech_stack_rules": [],
                "coding_rules": [],
                "decision_policies": [],
            },
        )
        assert resp.status_code == 404

    async def test_put_charter_invalid_body(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/projects",
            json={"name": "charter-invalid"},
        )
        project_id = create_resp.json()["id"]

        # goals should be list of strings, not a string
        resp = await client.put(
            f"/api/projects/{project_id}/charter",
            json={"goals": "not-a-list"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Unit tests: Engine knowledge context injection
# ---------------------------------------------------------------------------


class TestBuildKnowledgeContext:
    def test_empty_knowledge(self):
        assert build_knowledge_context({}) == ""

    def test_archetype_only_knowledge(self):
        knowledge = {
            "archetype_roles": ["developer"],
            "archetype_settings": {"auto_test": True},
        }
        assert build_knowledge_context(knowledge) == ""

    def test_knowledge_with_tech_stack(self):
        knowledge = {"tech_stack": {"language": "python", "framework": "fastapi"}}
        result = build_knowledge_context(knowledge)
        assert "## Project Knowledge" in result
        assert "Tech Stack" in result
        assert "python" in result
        assert "fastapi" in result

    def test_knowledge_with_charter(self):
        knowledge = {
            "charter": {
                "goals": ["Ship MVP"],
                "constraints": ["No external calls"],
                "tech_stack_rules": [],
                "coding_rules": ["Type hints required"],
                "decision_policies": [],
            }
        }
        result = build_knowledge_context(knowledge)
        assert "Agent Charter" in result
        assert "Ship MVP" in result
        assert "No external calls" in result
        assert "Type hints required" in result

    def test_knowledge_with_decisions(self):
        knowledge = {
            "decisions": [{"id": "D001", "title": "Use JSONB", "status": "accepted"}],
            "open_decisions": [{"id": "OD001", "question": "Which cache?"}],
        }
        result = build_knowledge_context(knowledge)
        assert "Use JSONB" in result
        assert "accepted" in result
        assert "Which cache?" in result

    def test_knowledge_full(self):
        knowledge = {
            "tech_stack": {"language": "python"},
            "architecture": {"pattern": "hexagonal"},
            "conventions": {"style": "black"},
            "decisions": [{"title": "D1", "status": "done"}],
            "open_decisions": [{"question": "Q1"}],
            "charter": {"goals": ["G1"], "constraints": ["C1"]},
            "archetype_roles": ["dev"],  # should be excluded
        }
        result = build_knowledge_context(knowledge)
        assert "## Project Knowledge" in result
        assert "python" in result
        assert "hexagonal" in result
        assert "black" in result
        assert "G1" in result
        assert "archetype_roles" not in result


@pytest.mark.asyncio
class TestEngineKnowledgeInjection:
    """Test that NativeEngine injects knowledge into the system prompt."""

    async def test_engine_includes_knowledge_in_system_prompt(self, db_session: AsyncSession):
        """When a session's project has knowledge, it appears in the system prompt."""
        from dataclasses import dataclass
        from codehive.engine import NativeEngine
        from codehive.execution.diff import DiffService
        from codehive.execution.file_ops import FileOps
        from codehive.execution.git_ops import GitOps
        from codehive.execution.shell import ShellRunner

        # Create project with knowledge
        proj = await create_project(db_session, name="eng-proj")
        proj.knowledge = {"tech_stack": {"language": "python"}}
        await db_session.commit()
        await db_session.refresh(proj)

        # Create a session row linked to the project
        session_row = SessionModel(
            project_id=proj.id,
            name="test-session",
            engine="native",
            mode="execution",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(session_row)
        await db_session.commit()
        await db_session.refresh(session_row)

        # Mock Anthropic response (text-only, no tool calls)
        @dataclass
        class TextBlock:
            type: str = "text"
            text: str = "Hello"

        @dataclass
        class MockResp:
            content: list = None  # type: ignore[assignment]
            stop_reason: str = "end_turn"

            def __post_init__(self):
                if self.content is None:
                    self.content = [TextBlock()]

        client_mock = AsyncMock()
        _resp = MockResp()

        class _Stream:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            @property
            def text_stream(self):
                async def _gen():
                    for b in _resp.content:
                        if b.type == "text":
                            yield b.text

                return _gen()

            async def get_final_message(self):
                return _resp

        client_mock.messages.stream = MagicMock(return_value=_Stream())

        engine = NativeEngine(
            client=client_mock,
            event_bus=AsyncMock(),
            file_ops=FileOps(Path("/tmp")),
            shell_runner=ShellRunner(),
            git_ops=GitOps(Path("/tmp")),
            diff_service=DiffService(),
        )

        events = []
        async for ev in engine.send_message(session_row.id, "hi", db=db_session):
            events.append(ev)

        # Verify the system prompt was passed with knowledge
        call_kwargs = client_mock.messages.stream.call_args
        assert "system" in call_kwargs.kwargs or (
            len(call_kwargs.args) > 0 and "system" in str(call_kwargs)
        )
        system_prompt = call_kwargs.kwargs.get("system", "")
        assert "Project Knowledge" in system_prompt
        assert "python" in system_prompt

    async def test_engine_no_knowledge_block_when_empty(self, db_session: AsyncSession):
        """When project knowledge is empty, no knowledge block in system prompt."""
        from dataclasses import dataclass
        from codehive.engine import NativeEngine
        from codehive.execution.diff import DiffService
        from codehive.execution.file_ops import FileOps
        from codehive.execution.git_ops import GitOps
        from codehive.execution.shell import ShellRunner

        proj = await create_project(db_session, name="eng-empty")

        session_row = SessionModel(
            project_id=proj.id,
            name="test-session-empty",
            engine="native",
            mode="execution",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(session_row)
        await db_session.commit()
        await db_session.refresh(session_row)

        @dataclass
        class TextBlock:
            type: str = "text"
            text: str = "Hello"

        @dataclass
        class MockResp:
            content: list = None  # type: ignore[assignment]
            stop_reason: str = "end_turn"

            def __post_init__(self):
                if self.content is None:
                    self.content = [TextBlock()]

        client_mock = AsyncMock()
        _resp2 = MockResp()

        class _Stream2:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            @property
            def text_stream(self):
                async def _gen():
                    for b in _resp2.content:
                        if b.type == "text":
                            yield b.text

                return _gen()

            async def get_final_message(self):
                return _resp2

        client_mock.messages.stream = MagicMock(return_value=_Stream2())

        engine = NativeEngine(
            client=client_mock,
            event_bus=AsyncMock(),
            file_ops=FileOps(Path("/tmp")),
            shell_runner=ShellRunner(),
            git_ops=GitOps(Path("/tmp")),
            diff_service=DiffService(),
        )

        events = []
        async for ev in engine.send_message(session_row.id, "hi", db=db_session):
            events.append(ev)

        call_kwargs = client_mock.messages.stream.call_args
        system_prompt = call_kwargs.kwargs.get("system", "")
        assert "Project Knowledge" not in system_prompt

    async def test_engine_includes_charter_in_system_prompt(self, db_session: AsyncSession):
        """When project has a charter, it appears in the system prompt."""
        from dataclasses import dataclass
        from codehive.engine import NativeEngine
        from codehive.execution.diff import DiffService
        from codehive.execution.file_ops import FileOps
        from codehive.execution.git_ops import GitOps
        from codehive.execution.shell import ShellRunner

        proj = await create_project(db_session, name="eng-charter")
        proj.knowledge = {
            "charter": {
                "goals": ["Ship MVP by Q2"],
                "constraints": ["No external API calls"],
            }
        }
        await db_session.commit()
        await db_session.refresh(proj)

        session_row = SessionModel(
            project_id=proj.id,
            name="test-session-charter",
            engine="native",
            mode="execution",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(session_row)
        await db_session.commit()
        await db_session.refresh(session_row)

        @dataclass
        class TextBlock:
            type: str = "text"
            text: str = "Hello"

        @dataclass
        class MockResp:
            content: list = None  # type: ignore[assignment]
            stop_reason: str = "end_turn"

            def __post_init__(self):
                if self.content is None:
                    self.content = [TextBlock()]

        client_mock = AsyncMock()
        _resp3 = MockResp()

        class _Stream3:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

            @property
            def text_stream(self):
                async def _gen():
                    for b in _resp3.content:
                        if b.type == "text":
                            yield b.text

                return _gen()

            async def get_final_message(self):
                return _resp3

        client_mock.messages.stream = MagicMock(return_value=_Stream3())

        engine = NativeEngine(
            client=client_mock,
            event_bus=AsyncMock(),
            file_ops=FileOps(Path("/tmp")),
            shell_runner=ShellRunner(),
            git_ops=GitOps(Path("/tmp")),
            diff_service=DiffService(),
        )

        events = []
        async for ev in engine.send_message(session_row.id, "hi", db=db_session):
            events.append(ev)

        call_kwargs = client_mock.messages.stream.call_args
        system_prompt = call_kwargs.kwargs.get("system", "")
        assert "Agent Charter" in system_prompt
        assert "Ship MVP by Q2" in system_prompt
        assert "No external API calls" in system_prompt
