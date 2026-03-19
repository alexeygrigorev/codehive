"""Tests for GitHub repo import endpoints (issue #126)."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.db.models import Base
from codehive.integrations.github.repos import (
    GhRepo,
    GhRepoList,
    GhStatus,
    check_gh_status,
    clone_repo,
    is_within_home,
    list_repos,
)

pytestmark = pytest.mark.usefixtures("_enable_auth")


@pytest.fixture(autouse=True)
def _enable_auth(monkeypatch):
    monkeypatch.setenv("CODEHIVE_AUTH_ENABLED", "true")


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
# Unit tests: service layer
# ---------------------------------------------------------------------------


class TestIsWithinHome:
    def test_home_itself(self):
        home = os.path.expanduser("~")
        assert is_within_home(home) is True

    def test_subdir_of_home(self):
        home = os.path.expanduser("~")
        assert is_within_home(os.path.join(home, "projects")) is True

    def test_outside_home(self):
        assert is_within_home("/etc") is False

    def test_traversal_attack(self):
        home = os.path.expanduser("~")
        assert is_within_home(os.path.join(home, "..", "etc")) is False


@pytest.mark.asyncio
class TestCheckGhStatus:
    async def test_gh_not_installed(self):
        async def mock_run(*args):
            raise FileNotFoundError()

        with patch("codehive.integrations.github.repos._run_gh", side_effect=mock_run):
            result = await check_gh_status()
        assert result.available is False
        assert result.authenticated is False
        assert "not installed" in result.error

    async def test_gh_installed_but_not_authenticated(self):
        call_count = 0

        async def mock_run(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (0, "gh version 2.87.0\n", "")
            return (1, "", "not logged in")

        with patch("codehive.integrations.github.repos._run_gh", side_effect=mock_run):
            result = await check_gh_status()
        assert result.available is True
        assert result.authenticated is False
        assert "not authenticated" in result.error

    async def test_gh_installed_and_authenticated(self):
        call_count = 0

        async def mock_run(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (0, "gh version 2.87.0\n", "")
            return (
                0,
                "",
                "Logged in to github.com account testuser (keyring)",
            )

        with patch("codehive.integrations.github.repos._run_gh", side_effect=mock_run):
            result = await check_gh_status()
        assert result.available is True
        assert result.authenticated is True
        assert result.username == "testuser"
        assert result.error is None


@pytest.mark.asyncio
class TestListRepos:
    async def test_list_repos_success(self):
        fake_output = json.dumps(
            [
                {
                    "name": "myrepo",
                    "nameWithOwner": "user/myrepo",
                    "description": "A test repo",
                    "primaryLanguage": {"name": "Python"},
                    "updatedAt": "2026-03-18T10:00:00Z",
                    "isPrivate": False,
                    "url": "https://github.com/user/myrepo",
                }
            ]
        )

        async def mock_run(*args):
            return (0, fake_output, "")

        with patch("codehive.integrations.github.repos._run_gh", side_effect=mock_run):
            result = await list_repos()
        assert result.total == 1
        assert result.repos[0].name == "myrepo"
        assert result.repos[0].language == "Python"
        assert result.repos[0].is_private is False

    async def test_list_repos_with_search_filter(self):
        fake_output = json.dumps(
            [
                {
                    "name": "alpha",
                    "nameWithOwner": "user/alpha",
                    "description": None,
                    "primaryLanguage": None,
                    "updatedAt": None,
                    "isPrivate": False,
                    "url": "https://github.com/user/alpha",
                },
                {
                    "name": "beta",
                    "nameWithOwner": "user/beta",
                    "description": None,
                    "primaryLanguage": None,
                    "updatedAt": None,
                    "isPrivate": True,
                    "url": "https://github.com/user/beta",
                },
            ]
        )

        async def mock_run(*args):
            return (0, fake_output, "")

        with patch("codehive.integrations.github.repos._run_gh", side_effect=mock_run):
            result = await list_repos(search="alph")
        assert result.total == 1
        assert result.repos[0].name == "alpha"

    async def test_list_repos_with_owner(self):
        async def mock_run(*args):
            # Verify owner is passed to gh CLI
            assert "myorg" in args
            return (0, "[]", "")

        with patch("codehive.integrations.github.repos._run_gh", side_effect=mock_run):
            result = await list_repos(owner="myorg")
        assert result.total == 0

    async def test_list_repos_failure(self):
        async def mock_run(*args):
            return (1, "", "API rate limit exceeded")

        with patch("codehive.integrations.github.repos._run_gh", side_effect=mock_run):
            with pytest.raises(RuntimeError, match="rate limit"):
                await list_repos()


@pytest.mark.asyncio
class TestCloneRepo:
    async def test_clone_to_existing_dir(self):
        home = os.path.expanduser("~")
        target = os.path.join(home, f".codehive-test-exists-{uuid.uuid4().hex[:8]}")
        os.makedirs(target, exist_ok=True)
        try:
            with pytest.raises(FileExistsError, match="already exists"):
                await clone_repo(repo_url="https://github.com/user/repo", destination=target)
        finally:
            shutil.rmtree(target, ignore_errors=True)

    async def test_clone_outside_home(self):
        with pytest.raises(ValueError, match="outside the home"):
            await clone_repo(
                repo_url="https://github.com/user/repo",
                destination="/etc/hacked",
            )

    async def test_clone_success(self):
        home = os.path.expanduser("~")
        target = os.path.join(home, f".codehive-test-clone-{uuid.uuid4().hex[:8]}")
        try:

            async def mock_run(*args):
                # Simulate clone by creating the dir
                os.makedirs(target, exist_ok=True)
                return (0, "", "")

            with patch("codehive.integrations.github.repos._run_gh", side_effect=mock_run):
                result = await clone_repo(
                    repo_url="https://github.com/user/repo",
                    destination=target,
                )
            assert result == os.path.normpath(target)
        finally:
            shutil.rmtree(target, ignore_errors=True)

    async def test_clone_gh_failure(self):
        home = os.path.expanduser("~")
        target = os.path.join(home, f".codehive-test-fail-{uuid.uuid4().hex[:8]}")
        try:

            async def mock_run(*args):
                return (1, "", "fatal: repository not found")

            with patch("codehive.integrations.github.repos._run_gh", side_effect=mock_run):
                with pytest.raises(RuntimeError, match="Clone failed"):
                    await clone_repo(
                        repo_url="https://github.com/user/nonexistent",
                        destination=target,
                    )
        finally:
            shutil.rmtree(target, ignore_errors=True)


# ---------------------------------------------------------------------------
# Integration tests: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGhStatusEndpoint:
    async def test_status_authenticated(self, client: AsyncClient):
        mock_status = GhStatus(
            available=True,
            authenticated=True,
            username="testuser",
            error=None,
        )
        with patch(
            "codehive.api.routes.github_repos.check_gh_status",
            new_callable=AsyncMock,
            return_value=mock_status,
        ):
            resp = await client.get("/api/github/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["authenticated"] is True
        assert data["username"] == "testuser"
        assert data["error"] is None

    async def test_status_not_installed(self, client: AsyncClient):
        mock_status = GhStatus(
            available=False,
            authenticated=False,
            username=None,
            error="gh CLI is not installed. Install it from https://cli.github.com/",
        )
        with patch(
            "codehive.api.routes.github_repos.check_gh_status",
            new_callable=AsyncMock,
            return_value=mock_status,
        ):
            resp = await client.get("/api/github/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert "not installed" in data["error"]


@pytest.mark.asyncio
class TestGhReposEndpoint:
    async def test_repos_list(self, client: AsyncClient):
        mock_result = GhRepoList(
            repos=[
                GhRepo(
                    name="myrepo",
                    full_name="user/myrepo",
                    description="Test",
                    language="Python",
                    updated_at="2026-03-18T10:00:00Z",
                    is_private=False,
                    clone_url="https://github.com/user/myrepo",
                ),
            ],
            owner="user",
            total=1,
        )
        with patch(
            "codehive.api.routes.github_repos.list_repos",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await client.get("/api/github/repos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["repos"][0]["name"] == "myrepo"
        assert data["repos"][0]["language"] == "Python"

    async def test_repos_with_owner_param(self, client: AsyncClient):
        mock_result = GhRepoList(repos=[], owner="myorg", total=0)
        with patch(
            "codehive.api.routes.github_repos.list_repos",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_fn:
            resp = await client.get("/api/github/repos", params={"owner": "myorg"})
        assert resp.status_code == 200
        mock_fn.assert_called_once_with(owner="myorg", search=None, limit=100)

    async def test_repos_with_search_param(self, client: AsyncClient):
        mock_result = GhRepoList(repos=[], owner="user", total=0)
        with patch(
            "codehive.api.routes.github_repos.list_repos",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_fn:
            resp = await client.get("/api/github/repos", params={"search": "test"})
        assert resp.status_code == 200
        mock_fn.assert_called_once_with(owner=None, search="test", limit=100)

    async def test_repos_failure_returns_502(self, client: AsyncClient):
        with patch(
            "codehive.api.routes.github_repos.list_repos",
            new_callable=AsyncMock,
            side_effect=RuntimeError("API error"),
        ):
            resp = await client.get("/api/github/repos")
        assert resp.status_code == 502


@pytest.mark.asyncio
class TestGhCloneEndpoint:
    async def test_clone_success(self, client: AsyncClient):
        home = os.path.expanduser("~")
        dest = os.path.join(home, f".codehive-test-api-clone-{uuid.uuid4().hex[:8]}")

        with patch(
            "codehive.api.routes.github_repos.clone_repo",
            new_callable=AsyncMock,
            return_value=dest,
        ):
            resp = await client.post(
                "/api/github/clone",
                json={
                    "repo_url": "https://github.com/user/myrepo",
                    "destination": dest,
                    "project_name": "myrepo",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cloned"] is True
        assert data["project_name"] == "myrepo"
        assert data["path"] == dest
        assert "project_id" in data

    async def test_clone_conflict(self, client: AsyncClient):
        with patch(
            "codehive.api.routes.github_repos.clone_repo",
            new_callable=AsyncMock,
            side_effect=FileExistsError("Destination directory already exists: /tmp/test"),
        ):
            resp = await client.post(
                "/api/github/clone",
                json={
                    "repo_url": "https://github.com/user/repo",
                    "destination": "/tmp/test",
                    "project_name": "test",
                },
            )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    async def test_clone_outside_home(self, client: AsyncClient):
        with patch(
            "codehive.api.routes.github_repos.clone_repo",
            new_callable=AsyncMock,
            side_effect=ValueError("Destination path is outside the home directory"),
        ):
            resp = await client.post(
                "/api/github/clone",
                json={
                    "repo_url": "https://github.com/user/repo",
                    "destination": "/etc/hacked",
                    "project_name": "test",
                },
            )
        assert resp.status_code == 403

    async def test_clone_runtime_error(self, client: AsyncClient):
        with patch(
            "codehive.api.routes.github_repos.clone_repo",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Clone failed: network error"),
        ):
            resp = await client.post(
                "/api/github/clone",
                json={
                    "repo_url": "https://github.com/user/repo",
                    "destination": "/tmp/test",
                    "project_name": "test",
                },
            )
        assert resp.status_code == 500
