"""Tests for context file detection and API endpoints."""

import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.context_files import (
    CONTEXT_FILE_PATTERNS,
    MAX_CONTEXT_FILE_SIZE,
    read_context_file,
    scan_context_files,
)
from codehive.db.models import Base

pytestmark = pytest.mark.usefixtures("_enable_auth")


@pytest.fixture(autouse=True)
def _enable_auth(monkeypatch):
    monkeypatch.setenv("CODEHIVE_AUTH_ENABLED", "true")


# ---------------------------------------------------------------------------
# DB / client fixtures (same pattern as test_projects.py)
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
        resp = await ac.post(
            "/api/auth/register",
            json={"email": "test@test.com", "username": "testuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


# ---------------------------------------------------------------------------
# Unit tests: scan_context_files
# ---------------------------------------------------------------------------


class TestScanContextFiles:
    def test_detects_root_level_files(self, tmp_path: Path):
        (tmp_path / "CLAUDE.md").write_text("hello")
        (tmp_path / ".cursorrules").write_text("rules")
        result = scan_context_files(str(tmp_path))
        paths = [r["path"] for r in result]
        assert "CLAUDE.md" in paths
        assert ".cursorrules" in paths

    def test_detects_nested_claude_directory(self, tmp_path: Path):
        claude_dir = tmp_path / ".claude" / "agents"
        claude_dir.mkdir(parents=True)
        (tmp_path / ".claude" / "CLAUDE.md").write_text("root claude")
        (claude_dir / "pm.md").write_text("pm agent")
        result = scan_context_files(str(tmp_path))
        paths = [r["path"] for r in result]
        assert ".claude/CLAUDE.md" in paths
        assert ".claude/agents/pm.md" in paths

    def test_empty_directory(self, tmp_path: Path):
        result = scan_context_files(str(tmp_path))
        assert result == []

    def test_nonexistent_directory(self):
        result = scan_context_files("/nonexistent/path/12345")
        assert result == []

    def test_excludes_large_files(self, tmp_path: Path):
        big_file = tmp_path / "CLAUDE.md"
        big_file.write_bytes(b"x" * (MAX_CONTEXT_FILE_SIZE + 1))
        result = scan_context_files(str(tmp_path))
        assert result == []

    def test_includes_size(self, tmp_path: Path):
        (tmp_path / "agent.md").write_text("hello world")
        result = scan_context_files(str(tmp_path))
        assert len(result) == 1
        assert result[0]["size"] == len("hello world")

    def test_detects_github_copilot_instructions(self, tmp_path: Path):
        gh_dir = tmp_path / ".github"
        gh_dir.mkdir()
        (gh_dir / "copilot-instructions.md").write_text("instructions")
        result = scan_context_files(str(tmp_path))
        paths = [r["path"] for r in result]
        assert ".github/copilot-instructions.md" in paths

    def test_detects_codex_and_cursor_dirs(self, tmp_path: Path):
        (tmp_path / ".codex").mkdir()
        (tmp_path / ".codex" / "config.yaml").write_text("cfg")
        (tmp_path / ".cursor").mkdir()
        (tmp_path / ".cursor" / "rules.json").write_text("{}")
        result = scan_context_files(str(tmp_path))
        paths = [r["path"] for r in result]
        assert ".codex/config.yaml" in paths
        assert ".cursor/rules.json" in paths


# ---------------------------------------------------------------------------
# Unit tests: read_context_file
# ---------------------------------------------------------------------------


class TestReadContextFile:
    def test_reads_valid_file(self, tmp_path: Path):
        (tmp_path / "CLAUDE.md").write_text("# Context")
        content = read_context_file(str(tmp_path), "CLAUDE.md")
        assert content == "# Context"

    def test_rejects_path_traversal(self, tmp_path: Path):
        with pytest.raises(ValueError, match="traversal"):
            read_context_file(str(tmp_path), "../../etc/passwd")

    def test_rejects_unknown_pattern(self, tmp_path: Path):
        (tmp_path / "random.txt").write_text("data")
        with pytest.raises(FileNotFoundError, match="not a known"):
            read_context_file(str(tmp_path), "random.txt")

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_context_file(str(tmp_path), "CLAUDE.md")

    def test_reads_nested_file(self, tmp_path: Path):
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "swe.md").write_text("engineer")
        content = read_context_file(str(tmp_path), ".claude/agents/swe.md")
        assert content == "engineer"


# ---------------------------------------------------------------------------
# Unit test: CONTEXT_FILE_PATTERNS is a single constant
# ---------------------------------------------------------------------------


class TestPatterns:
    def test_patterns_constant_exists(self):
        assert isinstance(CONTEXT_FILE_PATTERNS, list)
        assert len(CONTEXT_FILE_PATTERNS) > 0
        assert "CLAUDE.md" in CONTEXT_FILE_PATTERNS


# ---------------------------------------------------------------------------
# Integration tests: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestContextFilesAPI:
    async def test_list_context_files_200(self, client: AsyncClient, tmp_path: Path):
        # Create project with a real path
        (tmp_path / "CLAUDE.md").write_text("hello")
        (tmp_path / ".cursorrules").write_text("rules")

        resp = await client.post(
            "/api/projects",
            json={"name": "ctx-test", "path": str(tmp_path)},
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]

        resp = await client.get(f"/api/projects/{project_id}/context-files")
        assert resp.status_code == 200
        data = resp.json()
        paths = [f["path"] for f in data]
        assert "CLAUDE.md" in paths
        assert ".cursorrules" in paths

    async def test_list_context_files_no_path(self, client: AsyncClient):
        # Project without a path
        resp = await client.post(
            "/api/projects",
            json={"name": "no-path"},
        )
        project_id = resp.json()["id"]

        resp = await client.get(f"/api/projects/{project_id}/context-files")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_context_files_404(self, client: AsyncClient):
        resp = await client.get(f"/api/projects/{uuid.uuid4()}/context-files")
        assert resp.status_code == 404

    async def test_read_context_file_200(self, client: AsyncClient, tmp_path: Path):
        (tmp_path / "CLAUDE.md").write_text("# My Context")

        resp = await client.post(
            "/api/projects",
            json={"name": "read-test", "path": str(tmp_path)},
        )
        project_id = resp.json()["id"]

        resp = await client.get(f"/api/projects/{project_id}/context-files/CLAUDE.md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == "CLAUDE.md"
        assert data["content"] == "# My Context"

    async def test_read_context_file_path_traversal_400(self, client: AsyncClient, tmp_path: Path):
        # Create a subdir so the traversal resolves outside project root
        sub = tmp_path / "sub"
        sub.mkdir()
        resp = await client.post(
            "/api/projects",
            json={"name": "traversal-test", "path": str(sub)},
        )
        project_id = resp.json()["id"]

        # Write a CLAUDE.md in parent (outside project dir)
        (tmp_path / "CLAUDE.md").write_text("outside")

        # FastAPI path params decode %2F as /  so ../CLAUDE.md resolves outside
        resp = await client.get(f"/api/projects/{project_id}/context-files/..%2FCLAUDE.md")
        # Must not return 200 with the file content
        assert resp.status_code in (400, 404)
        if resp.status_code == 200:
            # Should never happen – this would be a security hole
            raise AssertionError("Path traversal returned file content!")

    async def test_read_context_file_not_found_404(self, client: AsyncClient, tmp_path: Path):
        resp = await client.post(
            "/api/projects",
            json={"name": "notfound-test", "path": str(tmp_path)},
        )
        project_id = resp.json()["id"]

        resp = await client.get(f"/api/projects/{project_id}/context-files/CLAUDE.md")
        assert resp.status_code == 404

    async def test_read_context_file_nonexistent_project_404(self, client: AsyncClient):
        resp = await client.get(f"/api/projects/{uuid.uuid4()}/context-files/CLAUDE.md")
        assert resp.status_code == 404
