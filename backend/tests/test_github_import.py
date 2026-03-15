"""Tests for GitHub issue import: client, mapper, importer, and API endpoints."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.db.models import Base, Issue, Project, Workspace
from codehive.integrations.github.client import GitHubAPIError, list_issues, get_issue
from codehive.integrations.github.importer import import_issues
from codehive.integrations.github.mapper import map_github_issue

# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database (same pattern as test_issues.py)
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

            columns.append(col_copy)

        from sqlalchemy import Table

        Table(table.name, metadata, *columns)

    return metadata


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create tables in an in-memory SQLite DB and yield an async session."""
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
    """Create a workspace for tests."""
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
    """Create a project for tests."""
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
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with the DB session overridden."""
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Sample GitHub issue data
# ---------------------------------------------------------------------------


def _gh_issue(
    number: int = 1,
    title: str = "Bug report",
    body: str | None = "Something is broken",
    state: str = "open",
    labels: list[dict] | None = None,
    is_pr: bool = False,
) -> dict:
    """Build a fake GitHub issue dict."""
    issue: dict = {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "labels": labels or [],
    }
    if is_pr:
        issue["pull_request"] = {"url": "https://api.github.com/repos/o/r/pulls/1"}
    return issue


# ===========================================================================
# Unit: GitHub client (integrations/github/client.py)
# ===========================================================================


def _mock_response(status_code: int, json_data, headers=None):
    """Create a Mock httpx response with sync .json() method."""
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    resp.headers = headers or {}
    return resp


def _mock_httpx_client(get_side_effect=None, get_return_value=None):
    """Create an AsyncMock httpx client that works as async context manager."""
    mock_client = AsyncMock()
    if get_side_effect is not None:
        mock_client.get.side_effect = get_side_effect
    elif get_return_value is not None:
        mock_client.get.return_value = get_return_value
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
class TestGitHubClient:
    async def test_list_issues_success(self):
        """list_issues returns parsed issue dicts on mocked 200 response."""
        resp = _mock_response(200, [_gh_issue(1), _gh_issue(2)])
        mock_client = _mock_httpx_client(get_return_value=resp)

        with patch(
            "codehive.integrations.github.client.httpx.AsyncClient", return_value=mock_client
        ):
            result = await list_issues("octocat", "Hello-World", "ghp_test")

        assert len(result) == 2
        assert result[0]["number"] == 1

    async def test_list_issues_filters_prs(self):
        """list_issues filters out pull requests."""
        resp = _mock_response(200, [_gh_issue(1), _gh_issue(2, is_pr=True), _gh_issue(3)])
        mock_client = _mock_httpx_client(get_return_value=resp)

        with patch(
            "codehive.integrations.github.client.httpx.AsyncClient", return_value=mock_client
        ):
            result = await list_issues("octocat", "Hello-World", "ghp_test")

        assert len(result) == 2
        numbers = [i["number"] for i in result]
        assert 2 not in numbers

    async def test_list_issues_pagination(self):
        """list_issues handles pagination via Link header."""
        page1 = _mock_response(
            200,
            [_gh_issue(1)],
            headers={"link": '<https://api.github.com/repos/o/r/issues?page=2>; rel="next"'},
        )
        page2 = _mock_response(200, [_gh_issue(2)])
        mock_client = _mock_httpx_client(get_side_effect=[page1, page2])

        with patch(
            "codehive.integrations.github.client.httpx.AsyncClient", return_value=mock_client
        ):
            result = await list_issues("octocat", "Hello-World", "ghp_test")

        assert len(result) == 2

    async def test_list_issues_with_since(self):
        """list_issues passes since as query param."""
        resp = _mock_response(200, [])
        mock_client = _mock_httpx_client(get_return_value=resp)

        with patch(
            "codehive.integrations.github.client.httpx.AsyncClient", return_value=mock_client
        ):
            await list_issues("o", "r", "t", since="2025-01-01T00:00:00Z")

        call_kwargs = mock_client.get.call_args
        assert "since" in call_kwargs.kwargs.get("params", {})

    async def test_list_issues_raises_on_401(self):
        """list_issues raises GitHubAPIError on 401."""
        resp = _mock_response(401, {"message": "Bad credentials"})
        mock_client = _mock_httpx_client(get_return_value=resp)

        with patch(
            "codehive.integrations.github.client.httpx.AsyncClient", return_value=mock_client
        ):
            with pytest.raises(GitHubAPIError) as exc_info:
                await list_issues("o", "r", "bad_token")
            assert exc_info.value.status_code == 401

    async def test_list_issues_raises_on_404(self):
        """list_issues raises GitHubAPIError on 404 (bad repo)."""
        resp = _mock_response(404, {"message": "Not Found"})
        mock_client = _mock_httpx_client(get_return_value=resp)

        with patch(
            "codehive.integrations.github.client.httpx.AsyncClient", return_value=mock_client
        ):
            with pytest.raises(GitHubAPIError) as exc_info:
                await list_issues("o", "bad-repo", "t")
            assert exc_info.value.status_code == 404

    async def test_get_issue_success(self):
        """get_issue returns a single issue dict on success."""
        resp = _mock_response(200, _gh_issue(42))
        mock_client = _mock_httpx_client(get_return_value=resp)

        with patch(
            "codehive.integrations.github.client.httpx.AsyncClient", return_value=mock_client
        ):
            result = await get_issue("o", "r", 42, "t")

        assert result["number"] == 42


# ===========================================================================
# Unit: Mapper (integrations/github/mapper.py)
# ===========================================================================


class TestMapper:
    def test_map_open_state(self):
        result = map_github_issue(_gh_issue(state="open"))
        assert result["status"] == "open"

    def test_map_closed_state(self):
        result = map_github_issue(_gh_issue(state="closed"))
        assert result["status"] == "closed"

    def test_truncates_long_title(self):
        long_title = "x" * 600
        result = map_github_issue(_gh_issue(title=long_title))
        assert len(result["title"]) == 500

    def test_labels_appended_to_description(self):
        labels = [{"name": "bug"}, {"name": "enhancement"}]
        result = map_github_issue(_gh_issue(body="body text", labels=labels))
        assert result["description"] is not None
        assert "Labels: bug, enhancement" in result["description"]
        assert result["description"].startswith("body text")

    def test_no_labels_leaves_description_as_is(self):
        result = map_github_issue(_gh_issue(body="just the body"))
        assert result["description"] == "just the body"

    def test_null_body_with_labels(self):
        labels = [{"name": "bug"}]
        result = map_github_issue(_gh_issue(body=None, labels=labels))
        assert result["description"] is not None
        assert "Labels: bug" in result["description"]

    def test_null_body_no_labels(self):
        result = map_github_issue(_gh_issue(body=None))
        assert result["description"] is None

    def test_github_issue_id_set(self):
        result = map_github_issue(_gh_issue(number=42))
        assert result["github_issue_id"] == 42


# ===========================================================================
# Unit: Importer (integrations/github/importer.py)
# ===========================================================================


@pytest.mark.asyncio
class TestImporter:
    async def test_creates_new_issues(self, db_session: AsyncSession, project: Project):
        """import_issues creates new internal issues for GitHub issues not yet imported."""

        async def fake_list_issues(owner, repo, token, *, since=None):
            return [_gh_issue(1, title="Issue 1"), _gh_issue(2, title="Issue 2")]

        result = await import_issues(
            db_session,
            project_id=project.id,
            owner="o",
            repo="r",
            token="t",
            _list_issues=fake_list_issues,
        )

        assert result.created == 2
        assert result.updated == 0
        assert result.errors == []

    async def test_updates_existing_issues(self, db_session: AsyncSession, project: Project):
        """import_issues updates existing issues when github_issue_id matches."""

        async def fake_list_issues(owner, repo, token, *, since=None):
            return [_gh_issue(1, title="Original")]

        # First import
        await import_issues(
            db_session,
            project_id=project.id,
            owner="o",
            repo="r",
            token="t",
            _list_issues=fake_list_issues,
        )

        # Second import with updated title
        async def fake_list_issues_v2(owner, repo, token, *, since=None):
            return [_gh_issue(1, title="Updated")]

        result = await import_issues(
            db_session,
            project_id=project.id,
            owner="o",
            repo="r",
            token="t",
            _list_issues=fake_list_issues_v2,
        )

        assert result.created == 0
        assert result.updated == 1

    async def test_import_result_counts(self, db_session: AsyncSession, project: Project):
        """import_issues returns correct ImportResult counts."""
        # Pre-create one issue
        issue = Issue(
            project_id=project.id,
            title="Existing",
            status="open",
            github_issue_id=1,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(issue)
        await db_session.commit()

        async def fake_list_issues(owner, repo, token, *, since=None):
            return [
                _gh_issue(1, title="Updated existing"),
                _gh_issue(2, title="Brand new"),
            ]

        result = await import_issues(
            db_session,
            project_id=project.id,
            owner="o",
            repo="r",
            token="t",
            _list_issues=fake_list_issues,
        )

        assert result.created == 1
        assert result.updated == 1

    async def test_records_errors(self, db_session: AsyncSession, project: Project):
        """import_issues records errors when individual issue creation fails."""

        async def fake_list_issues(owner, repo, token, *, since=None):
            # Return an issue missing 'number' key to trigger an error in mapper
            return [{"title": "Bad issue", "state": "open", "body": None, "labels": []}]

        result = await import_issues(
            db_session,
            project_id=project.id,
            owner="o",
            repo="r",
            token="t",
            _list_issues=fake_list_issues,
        )

        assert len(result.errors) == 1

    async def test_passes_since_to_client(self, db_session: AsyncSession, project: Project):
        """import_issues passes since to the client's list_issues."""
        received_since = {}

        async def fake_list_issues(owner, repo, token, *, since=None):
            received_since["value"] = since
            return []

        await import_issues(
            db_session,
            project_id=project.id,
            owner="o",
            repo="r",
            token="t",
            since="2025-06-01T00:00:00Z",
            _list_issues=fake_list_issues,
        )

        assert received_since["value"] == "2025-06-01T00:00:00Z"


# ===========================================================================
# Integration: API endpoints via AsyncClient
# ===========================================================================


@pytest.mark.asyncio
class TestConfigureEndpoint:
    async def test_configure_200_masked_token(self, client: AsyncClient, project: Project):
        resp = await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={"owner": "octocat", "repo": "Hello-World", "token": "ghp_abc123xyz"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["owner"] == "octocat"
        assert data["repo"] == "Hello-World"
        assert data["token_masked"] == "ghp_***"
        assert "abc123xyz" not in data["token_masked"]

    async def test_configure_nonexistent_project_404(self, client: AsyncClient):
        resp = await client.post(
            f"/api/projects/{uuid.uuid4()}/github/configure",
            json={"owner": "o", "repo": "r", "token": "t"},
        )
        assert resp.status_code == 404

    async def test_configure_missing_fields_422(self, client: AsyncClient, project: Project):
        resp = await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={"owner": "o"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestStatusEndpoint:
    async def test_status_not_configured(self, client: AsyncClient, project: Project):
        resp = await client.get(f"/api/projects/{project.id}/github/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False

    async def test_status_after_configure(self, client: AsyncClient, project: Project):
        # Configure first
        await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={"owner": "octocat", "repo": "Hello-World", "token": "ghp_secret"},
        )

        resp = await client.get(f"/api/projects/{project.id}/github/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is True
        assert data["owner"] == "octocat"
        assert data["repo"] == "Hello-World"
        assert data["token_masked"] == "ghp_***"
        assert data["last_import_at"] is None

    async def test_status_nonexistent_project_404(self, client: AsyncClient):
        resp = await client.get(f"/api/projects/{uuid.uuid4()}/github/status")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestImportEndpoint:
    async def test_import_success(self, client: AsyncClient, project: Project):
        """POST import with mocked GitHub client returns 200 with counts."""
        # Configure
        await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={"owner": "o", "repo": "r", "token": "t"},
        )

        fake_gh_issues = [_gh_issue(1, title="GH Issue 1"), _gh_issue(2, title="GH Issue 2")]

        with patch(
            "codehive.integrations.github.importer.gh_client.list_issues",
            new_callable=AsyncMock,
            return_value=fake_gh_issues,
        ):
            resp = await client.post(f"/api/projects/{project.id}/github/import")

        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 2
        assert data["updated"] == 0
        assert data["errors"] == []

    async def test_import_without_configure_400(self, client: AsyncClient, project: Project):
        resp = await client.post(f"/api/projects/{project.id}/github/import")
        assert resp.status_code == 400

    async def test_import_nonexistent_project_404(self, client: AsyncClient):
        resp = await client.post(f"/api/projects/{uuid.uuid4()}/github/import")
        assert resp.status_code == 404

    async def test_import_twice_no_duplicates(self, client: AsyncClient, project: Project):
        """Import twice with same issues: first creates, second updates."""
        await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={"owner": "o", "repo": "r", "token": "t"},
        )

        fake_gh_issues = [_gh_issue(1, title="GH Issue 1")]

        with patch(
            "codehive.integrations.github.importer.gh_client.list_issues",
            new_callable=AsyncMock,
            return_value=fake_gh_issues,
        ):
            resp1 = await client.post(f"/api/projects/{project.id}/github/import")
            assert resp1.json()["created"] == 1

            resp2 = await client.post(f"/api/projects/{project.id}/github/import")
            assert resp2.json()["created"] == 0
            assert resp2.json()["updated"] == 1

    async def test_import_with_since(self, client: AsyncClient, project: Project):
        """POST import with since parameter passes it through."""
        await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={"owner": "o", "repo": "r", "token": "t"},
        )

        mock_list = AsyncMock(return_value=[])

        with patch(
            "codehive.integrations.github.importer.gh_client.list_issues",
            mock_list,
        ):
            resp = await client.post(
                f"/api/projects/{project.id}/github/import",
                json={"since": "2025-01-01T00:00:00Z"},
            )

        assert resp.status_code == 200
        mock_list.assert_called_once_with("o", "r", "t", since="2025-01-01T00:00:00Z")

    async def test_imported_issues_visible_via_issues_api(
        self, client: AsyncClient, project: Project
    ):
        """Imported issues are visible via GET /api/projects/{id}/issues."""
        await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={"owner": "o", "repo": "r", "token": "t"},
        )

        fake_gh_issues = [_gh_issue(42, title="From GitHub")]

        with patch(
            "codehive.integrations.github.importer.gh_client.list_issues",
            new_callable=AsyncMock,
            return_value=fake_gh_issues,
        ):
            await client.post(f"/api/projects/{project.id}/github/import")

        resp = await client.get(f"/api/projects/{project.id}/issues")
        assert resp.status_code == 200
        issues = resp.json()
        assert len(issues) == 1
        assert issues[0]["title"] == "From GitHub"
        assert issues[0]["github_issue_id"] == 42


@pytest.mark.asyncio
class TestGitHubRouterRegistered:
    async def test_endpoints_respond(self, client: AsyncClient, project: Project):
        """GitHub router is registered and endpoints respond (not 404 from missing route)."""
        # Status endpoint should work (not a router-missing 404)
        resp = await client.get(f"/api/projects/{project.id}/github/status")
        assert resp.status_code == 200

        # Configure should work
        resp = await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={"owner": "o", "repo": "r", "token": "t"},
        )
        assert resp.status_code == 200

        # Import should work (400 is expected since we just configured -- but NOT 404)
        # Actually since we just configured, it should try to import.
        # Let's just verify it's not a 404 from route not found.
        # We already configured, so mock the client.
        with patch(
            "codehive.integrations.github.importer.gh_client.list_issues",
            new_callable=AsyncMock,
            return_value=[],
        ):
            resp = await client.post(f"/api/projects/{project.id}/github/import")
        assert resp.status_code == 200
