"""Tests for directory picker endpoints and git_init logic (issue #125)."""

import os
import shutil
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
from codehive.core.project import ensure_directory_with_git
from codehive.db.models import Base

pytestmark = pytest.mark.usefixtures("_enable_auth")


@pytest.fixture(autouse=True)
def _enable_auth(monkeypatch):
    monkeypatch.setenv("CODEHIVE_AUTH_ENABLED", "true")


SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def home_tmp_path():
    """Create a temporary directory under $HOME for tests that need home-relative paths."""
    home = os.path.expanduser("~")
    dirname = f".codehive-test-{uuid.uuid4().hex[:8]}"
    path = Path(home) / dirname
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


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
# Unit tests: ensure_directory_with_git
# ---------------------------------------------------------------------------


class TestEnsureDirectoryWithGit:
    def test_creates_directory(self, tmp_path):
        target = str(tmp_path / "newdir")
        ensure_directory_with_git(target, git_init=False)
        assert os.path.isdir(target)
        assert not os.path.isdir(os.path.join(target, ".git"))

    def test_creates_directory_with_git_init(self, tmp_path):
        target = str(tmp_path / "newgit")
        ensure_directory_with_git(target, git_init=True)
        assert os.path.isdir(target)
        assert os.path.isdir(os.path.join(target, ".git"))

    def test_git_init_skipped_when_already_exists(self, tmp_path):
        target = str(tmp_path / "existing")
        os.makedirs(os.path.join(target, ".git"))
        # Should not error even with git_init=True
        ensure_directory_with_git(target, git_init=True)
        assert os.path.isdir(os.path.join(target, ".git"))

    def test_existing_directory_no_error(self, tmp_path):
        target = str(tmp_path / "existing2")
        os.makedirs(target)
        ensure_directory_with_git(target, git_init=False)
        assert os.path.isdir(target)


# ---------------------------------------------------------------------------
# Integration tests: default-directory endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDefaultDirectoryEndpoint:
    async def test_returns_default_directory(self, client: AsyncClient, monkeypatch):
        monkeypatch.setenv("CODEHIVE_PROJECTS_DIR", "/tmp/test-codehive")
        resp = await client.get("/api/system/default-directory")
        assert resp.status_code == 200
        data = resp.json()
        assert "default_directory" in data
        # Should be a non-empty string
        assert len(data["default_directory"]) > 0


# ---------------------------------------------------------------------------
# Integration tests: directories endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDirectoriesEndpoint:
    async def test_list_directories(self, client: AsyncClient, home_tmp_path):
        """List subdirectories at a valid path under home."""
        subdir = home_tmp_path / "child"
        subdir.mkdir()

        resp = await client.get(
            "/api/system/directories",
            params={"path": str(home_tmp_path)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == str(home_tmp_path)
        names = [d["name"] for d in data["directories"]]
        assert "child" in names

    async def test_rejects_path_outside_home(self, client: AsyncClient):
        """Paths outside the home directory should return 403."""
        resp = await client.get(
            "/api/system/directories",
            params={"path": "/etc"},
        )
        assert resp.status_code == 403

    async def test_nonexistent_path_returns_404(self, client: AsyncClient):
        """A path that does not exist should return 404."""
        home = os.path.expanduser("~")
        fake = os.path.join(home, f"nonexistent-{uuid.uuid4()}")
        resp = await client.get(
            "/api/system/directories",
            params={"path": fake},
        )
        assert resp.status_code == 404

    async def test_hidden_directories_excluded(self, client: AsyncClient, home_tmp_path):
        """Hidden directories (starting with .) should not be listed."""
        (home_tmp_path / ".hidden").mkdir()
        (home_tmp_path / "visible").mkdir()

        resp = await client.get(
            "/api/system/directories",
            params={"path": str(home_tmp_path)},
        )
        assert resp.status_code == 200
        names = [d["name"] for d in resp.json()["directories"]]
        assert "visible" in names
        assert ".hidden" not in names

    async def test_has_git_detection(self, client: AsyncClient, home_tmp_path):
        """Directories with .git/ should have has_git=True."""
        git_dir = home_tmp_path / "with-git"
        git_dir.mkdir()
        (git_dir / ".git").mkdir()

        no_git_dir = home_tmp_path / "without-git"
        no_git_dir.mkdir()

        resp = await client.get(
            "/api/system/directories",
            params={"path": str(home_tmp_path)},
        )
        assert resp.status_code == 200
        dirs = {d["name"]: d for d in resp.json()["directories"]}
        assert dirs["with-git"]["has_git"] is True
        assert dirs["without-git"]["has_git"] is False

    async def test_parent_field_present(self, client: AsyncClient, home_tmp_path):
        """Response should include parent directory."""
        resp = await client.get(
            "/api/system/directories",
            params={"path": str(home_tmp_path)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["parent"] is not None
        assert data["parent"] == str(home_tmp_path.parent)


# ---------------------------------------------------------------------------
# Integration tests: POST /api/projects with git_init
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateProjectWithGitInit:
    async def test_create_project_with_git_init_true(self, client: AsyncClient, tmp_path):
        target = str(tmp_path / "new-project")
        resp = await client.post(
            "/api/projects",
            json={
                "name": "test-git-init",
                "path": target,
                "git_init": True,
            },
        )
        assert resp.status_code == 201
        assert os.path.isdir(target)
        assert os.path.isdir(os.path.join(target, ".git"))

    async def test_create_project_with_git_init_false(self, client: AsyncClient, tmp_path):
        target = str(tmp_path / "no-git-project")
        resp = await client.post(
            "/api/projects",
            json={
                "name": "test-no-git",
                "path": target,
                "git_init": False,
            },
        )
        assert resp.status_code == 201
        assert os.path.isdir(target)
        assert not os.path.isdir(os.path.join(target, ".git"))

    async def test_create_project_without_git_init_field(self, client: AsyncClient, tmp_path):
        """When git_init is omitted, it defaults to False."""
        target = str(tmp_path / "default-project")
        resp = await client.post(
            "/api/projects",
            json={
                "name": "test-default",
                "path": target,
            },
        )
        assert resp.status_code == 201
        assert os.path.isdir(target)
        assert not os.path.isdir(os.path.join(target, ".git"))

    async def test_create_project_no_path_skips_directory_logic(self, client: AsyncClient):
        """When path is None, no directory creation is attempted."""
        resp = await client.post(
            "/api/projects",
            json={
                "name": "no-path-project",
                "git_init": True,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "no-path-project"
