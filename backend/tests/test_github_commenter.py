"""Tests for GitHub pipeline commenter, label filtering, and orchestrator integration."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.db.models import Base, Issue, Project, Session, Task
from codehive.integrations.github.client import GitHubAPIError
from codehive.integrations.github.commenter import (
    build_pipeline_message,
    post_pipeline_comment,
)
from codehive.integrations.github.importer import import_issues
from codehive.integrations.github.triggers import (
    _issue_matches_labels,
    handle_issue_event,
)
from codehive.integrations.github.webhook import WebhookEvent

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(db_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with db_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def project(db_session: AsyncSession) -> Project:
    proj = Project(
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

WEBHOOK_SECRET = "test-secret-key"


def _sign_payload(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    import hashlib
    import hmac as _hmac

    mac = _hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def _gh_issue(
    number: int = 1,
    title: str = "Bug report",
    body: str | None = "Something is broken",
    state: str = "open",
    labels: list[dict] | None = None,
) -> dict:
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "labels": labels or [],
    }


def _gh_webhook_payload(
    *,
    action: str = "opened",
    number: int = 42,
    title: str = "Fix login bug",
    body: str | None = "Description of the bug",
    state: str = "open",
    labels: list[dict] | None = None,
    owner: str = "octocat",
    repo: str = "Hello-World",
) -> dict:
    return {
        "action": action,
        "issue": {
            "number": number,
            "title": title,
            "body": body,
            "state": state,
            "labels": labels or [],
        },
        "repository": {
            "name": repo,
            "owner": {"login": owner},
        },
    }


def _mock_httpx_client(post_return_value=None):
    """Create an AsyncMock httpx client for POST requests."""
    mock_client = AsyncMock()
    if post_return_value is not None:
        mock_client.post.return_value = post_return_value
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _mock_response(status_code: int, json_data=None, text=""):
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text or str(json_data)
    return resp


async def _configure_project(
    client: AsyncClient,
    project_id: uuid.UUID,
    *,
    owner: str = "octocat",
    repo: str = "Hello-World",
    token: str = "ghp_test123",
    webhook_secret: str | None = WEBHOOK_SECRET,
    trigger_mode: str = "manual",
    sync_labels: list[str] | None = None,
) -> None:
    body: dict = {"owner": owner, "repo": repo, "token": token, "trigger_mode": trigger_mode}
    if webhook_secret is not None:
        body["webhook_secret"] = webhook_secret
    if sync_labels is not None:
        body["sync_labels"] = sync_labels
    resp = await client.post(f"/api/projects/{project_id}/github/configure", json=body)
    assert resp.status_code == 200


async def _post_webhook(
    client: AsyncClient,
    payload: dict,
    *,
    event_type: str = "issues",
    secret: str | None = WEBHOOK_SECRET,
):
    raw = json.dumps(payload).encode("utf-8")
    headers = {"X-GitHub-Event": event_type, "Content-Type": "application/json"}
    if secret is not None:
        headers["X-Hub-Signature-256"] = _sign_payload(raw, secret)
    return await client.post("/api/webhooks/github", content=raw, headers=headers)


# ===========================================================================
# Unit: build_pipeline_message
# ===========================================================================


class TestBuildPipelineMessage:
    def test_grooming(self):
        assert build_pipeline_message("grooming") == "[Codehive] Pipeline: grooming started."

    def test_implementing(self):
        msg = build_pipeline_message("implementing")
        assert msg == "[Codehive] Pipeline: implementation started."

    def test_testing(self):
        assert build_pipeline_message("testing") == "[Codehive] Pipeline: testing started."

    def test_accepting(self):
        assert build_pipeline_message("accepting") == "[Codehive] Pipeline: review started."

    def test_done_without_sha(self):
        assert build_pipeline_message("done") == "[Codehive] Pipeline: done."

    def test_done_with_sha(self):
        msg = build_pipeline_message("done", commit_sha="abc1234")
        assert msg == "[Codehive] Pipeline: done. Commit: abc1234."

    def test_unknown_step_uses_raw_name(self):
        msg = build_pipeline_message("custom_step")
        assert msg == "[Codehive] Pipeline: custom_step."


# ===========================================================================
# Unit: post_pipeline_comment
# ===========================================================================


@pytest.mark.asyncio
class TestPostPipelineComment:
    async def test_posts_to_correct_url(self):
        resp = _mock_response(201)
        mock_client = _mock_httpx_client(post_return_value=resp)

        with patch(
            "codehive.integrations.github.commenter.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await post_pipeline_comment("octocat", "Hello-World", 42, "ghp_test", "Test message")

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/repos/octocat/Hello-World/issues/42/comments" in call_args.args[0]
        assert call_args.kwargs["json"] == {"body": "Test message"}

    async def test_raises_on_401(self):
        resp = _mock_response(401, text="Bad credentials")
        mock_client = _mock_httpx_client(post_return_value=resp)

        with patch(
            "codehive.integrations.github.commenter.httpx.AsyncClient",
            return_value=mock_client,
        ):
            with pytest.raises(GitHubAPIError) as exc_info:
                await post_pipeline_comment("o", "r", 1, "bad_token", "msg")
            assert exc_info.value.status_code == 401

    async def test_raises_on_404(self):
        resp = _mock_response(404, text="Not Found")
        mock_client = _mock_httpx_client(post_return_value=resp)

        with patch(
            "codehive.integrations.github.commenter.httpx.AsyncClient",
            return_value=mock_client,
        ):
            with pytest.raises(GitHubAPIError) as exc_info:
                await post_pipeline_comment("o", "r", 999, "token", "msg")
            assert exc_info.value.status_code == 404

    async def test_succeeds_on_201(self):
        resp = _mock_response(201)
        mock_client = _mock_httpx_client(post_return_value=resp)

        with patch(
            "codehive.integrations.github.commenter.httpx.AsyncClient",
            return_value=mock_client,
        ):
            # Should not raise
            await post_pipeline_comment("o", "r", 1, "token", "msg")


# ===========================================================================
# Unit: _issue_matches_labels helper
# ===========================================================================


class TestIssueMatchesLabels:
    def test_empty_sync_labels_matches_all(self):
        assert _issue_matches_labels({"labels": []}, []) is True
        assert _issue_matches_labels({"labels": [{"name": "bug"}]}, []) is True

    def test_matching_label(self):
        issue = {"labels": [{"name": "codehive"}, {"name": "bug"}]}
        assert _issue_matches_labels(issue, ["codehive"]) is True

    def test_no_matching_label(self):
        issue = {"labels": [{"name": "bug"}, {"name": "enhancement"}]}
        assert _issue_matches_labels(issue, ["codehive"]) is False

    def test_multiple_sync_labels_one_matches(self):
        issue = {"labels": [{"name": "auto-solve"}]}
        assert _issue_matches_labels(issue, ["codehive", "auto-solve"]) is True

    def test_issue_with_no_labels(self):
        issue = {"labels": []}
        assert _issue_matches_labels(issue, ["codehive"]) is False


# ===========================================================================
# Unit: Label filtering in triggers
# ===========================================================================


@pytest.mark.asyncio
class TestTriggerLabelFiltering:
    async def test_sync_labels_match_imports(self, db_session: AsyncSession, project: Project):
        payload = _gh_webhook_payload(labels=[{"name": "codehive"}])
        event = WebhookEvent(event_type="issues", action="opened", payload=payload)
        result = await handle_issue_event(
            db_session, project.id, event, "manual", sync_labels=["codehive"]
        )
        assert result.action_taken == "imported"
        assert result.issue_id is not None

    async def test_sync_labels_no_match_filtered(self, db_session: AsyncSession, project: Project):
        payload = _gh_webhook_payload(labels=[{"name": "bug"}, {"name": "enhancement"}])
        event = WebhookEvent(event_type="issues", action="opened", payload=payload)
        result = await handle_issue_event(
            db_session, project.id, event, "manual", sync_labels=["codehive"]
        )
        assert result.action_taken == "filtered"
        assert result.issue_id is None

    async def test_empty_sync_labels_imports_all(self, db_session: AsyncSession, project: Project):
        payload = _gh_webhook_payload(labels=[{"name": "anything"}])
        event = WebhookEvent(event_type="issues", action="opened", payload=payload)
        result = await handle_issue_event(db_session, project.id, event, "manual", sync_labels=[])
        assert result.action_taken == "imported"

    async def test_no_sync_labels_kwarg_imports_all(
        self, db_session: AsyncSession, project: Project
    ):
        payload = _gh_webhook_payload()
        event = WebhookEvent(event_type="issues", action="opened", payload=payload)
        result = await handle_issue_event(db_session, project.id, event, "manual")
        assert result.action_taken == "imported"

    async def test_multiple_sync_labels_one_matches(
        self, db_session: AsyncSession, project: Project
    ):
        payload = _gh_webhook_payload(labels=[{"name": "auto-solve"}])
        event = WebhookEvent(event_type="issues", action="opened", payload=payload)
        result = await handle_issue_event(
            db_session, project.id, event, "manual", sync_labels=["codehive", "auto-solve"]
        )
        assert result.action_taken == "imported"


# ===========================================================================
# Unit: Label filtering in importer
# ===========================================================================


@pytest.mark.asyncio
class TestImporterLabelFiltering:
    async def test_sync_labels_skips_non_matching(self, db_session: AsyncSession, project: Project):
        async def fake_list(owner, repo, token, *, since=None):
            return [
                _gh_issue(1, title="Has label", labels=[{"name": "codehive"}]),
                _gh_issue(2, title="No label", labels=[{"name": "bug"}]),
                _gh_issue(3, title="Also has label", labels=[{"name": "codehive"}]),
            ]

        result = await import_issues(
            db_session,
            project_id=project.id,
            owner="o",
            repo="r",
            token="t",
            sync_labels=["codehive"],
            _list_issues=fake_list,
        )
        assert result.created == 2
        assert result.updated == 0

    async def test_sync_labels_imports_matching(self, db_session: AsyncSession, project: Project):
        async def fake_list(owner, repo, token, *, since=None):
            return [_gh_issue(1, title="Match", labels=[{"name": "codehive"}])]

        result = await import_issues(
            db_session,
            project_id=project.id,
            owner="o",
            repo="r",
            token="t",
            sync_labels=["codehive"],
            _list_issues=fake_list,
        )
        assert result.created == 1

    async def test_empty_sync_labels_imports_all(self, db_session: AsyncSession, project: Project):
        async def fake_list(owner, repo, token, *, since=None):
            return [
                _gh_issue(1, title="A", labels=[]),
                _gh_issue(2, title="B", labels=[{"name": "bug"}]),
            ]

        result = await import_issues(
            db_session,
            project_id=project.id,
            owner="o",
            repo="r",
            token="t",
            sync_labels=[],
            _list_issues=fake_list,
        )
        assert result.created == 2


# ===========================================================================
# Unit: Orchestrator pipeline comment posting
# ===========================================================================


@pytest.mark.asyncio
class TestOrchestratorCommenter:
    async def test_comment_posted_on_grooming(
        self, db_session: AsyncSession, db_session_factory, project: Project
    ):
        """After pipeline transition to grooming, commenter is called."""
        from codehive.core.orchestrator_service import OrchestratorService

        # Create issue with github_issue_id
        project.github_config = {
            "owner": "octocat",
            "repo": "Hello-World",
            "token": "ghp_test",
        }
        db_session.add(project)
        await db_session.commit()

        issue = Issue(
            project_id=project.id,
            title="GH Issue",
            status="open",
            github_issue_id=42,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(issue)
        await db_session.commit()
        await db_session.refresh(issue)

        # Create session linked to issue
        session = Session(
            project_id=project.id,
            issue_id=issue.id,
            name="test-session",
            engine="native",
            mode="execution",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create task linked to session
        task = Task(
            session_id=session.id,
            title="Test task",
            pipeline_status="backlog",
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        orch = OrchestratorService(db_session_factory, project.id)

        with patch(
            "codehive.core.orchestrator_service.post_pipeline_comment",
            new_callable=AsyncMock,
        ) as mock_comment:
            await orch._try_post_github_comment(task.id, "grooming")

        mock_comment.assert_called_once_with(
            "octocat",
            "Hello-World",
            42,
            "ghp_test",
            "[Codehive] Pipeline: grooming started.",
        )

    async def test_comment_with_commit_sha_on_done(
        self, db_session: AsyncSession, db_session_factory, project: Project
    ):
        """After pipeline transition to done, commenter includes commit SHA."""
        from codehive.core.orchestrator_service import OrchestratorService

        project.github_config = {
            "owner": "octocat",
            "repo": "Hello-World",
            "token": "ghp_test",
        }
        db_session.add(project)
        await db_session.commit()

        issue = Issue(
            project_id=project.id,
            title="GH Issue",
            status="open",
            github_issue_id=42,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(issue)
        await db_session.commit()
        await db_session.refresh(issue)

        session = Session(
            project_id=project.id,
            issue_id=issue.id,
            name="test-session",
            engine="native",
            mode="execution",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        task = Task(
            session_id=session.id,
            title="Test task",
            pipeline_status="backlog",
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        orch = OrchestratorService(db_session_factory, project.id)

        with patch(
            "codehive.core.orchestrator_service.post_pipeline_comment",
            new_callable=AsyncMock,
        ) as mock_comment:
            await orch._try_post_github_comment(task.id, "done", commit_sha="abc1234")

        mock_comment.assert_called_once_with(
            "octocat",
            "Hello-World",
            42,
            "ghp_test",
            "[Codehive] Pipeline: done. Commit: abc1234.",
        )

    async def test_commenter_failure_does_not_break_pipeline(
        self, db_session: AsyncSession, db_session_factory, project: Project
    ):
        """If commenter raises, the pipeline continues (error logged, not re-raised)."""
        from codehive.core.orchestrator_service import OrchestratorService

        project.github_config = {
            "owner": "octocat",
            "repo": "Hello-World",
            "token": "ghp_test",
        }
        db_session.add(project)
        await db_session.commit()

        issue = Issue(
            project_id=project.id,
            title="GH Issue",
            status="open",
            github_issue_id=42,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(issue)
        await db_session.commit()
        await db_session.refresh(issue)

        session = Session(
            project_id=project.id,
            issue_id=issue.id,
            name="test-session",
            engine="native",
            mode="execution",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        task = Task(
            session_id=session.id,
            title="Test task",
            pipeline_status="backlog",
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        orch = OrchestratorService(db_session_factory, project.id)

        with patch(
            "codehive.core.orchestrator_service.post_pipeline_comment",
            new_callable=AsyncMock,
            side_effect=GitHubAPIError(500, "Internal Server Error"),
        ):
            # Should NOT raise
            await orch._try_post_github_comment(task.id, "grooming")

    async def test_no_github_issue_id_skips_comment(
        self, db_session: AsyncSession, db_session_factory, project: Project
    ):
        """For a task whose issue has no github_issue_id, commenter is NOT called."""
        from codehive.core.orchestrator_service import OrchestratorService

        project.github_config = {
            "owner": "octocat",
            "repo": "Hello-World",
            "token": "ghp_test",
        }
        db_session.add(project)
        await db_session.commit()

        # Issue WITHOUT github_issue_id
        issue = Issue(
            project_id=project.id,
            title="Local Issue",
            status="open",
            github_issue_id=None,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(issue)
        await db_session.commit()
        await db_session.refresh(issue)

        session = Session(
            project_id=project.id,
            issue_id=issue.id,
            name="test-session",
            engine="native",
            mode="execution",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        task = Task(
            session_id=session.id,
            title="Test task",
            pipeline_status="backlog",
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        orch = OrchestratorService(db_session_factory, project.id)

        with patch(
            "codehive.core.orchestrator_service.post_pipeline_comment",
            new_callable=AsyncMock,
        ) as mock_comment:
            await orch._try_post_github_comment(task.id, "grooming")

        mock_comment.assert_not_called()

    async def test_no_linked_issue_skips_comment(
        self, db_session: AsyncSession, db_session_factory, project: Project
    ):
        """For a task with no linked issue, commenter is NOT called."""
        from codehive.core.orchestrator_service import OrchestratorService

        # Session without issue_id
        session = Session(
            project_id=project.id,
            issue_id=None,
            name="test-session",
            engine="native",
            mode="execution",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        task = Task(
            session_id=session.id,
            title="Test task",
            pipeline_status="backlog",
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        orch = OrchestratorService(db_session_factory, project.id)

        with patch(
            "codehive.core.orchestrator_service.post_pipeline_comment",
            new_callable=AsyncMock,
        ) as mock_comment:
            await orch._try_post_github_comment(task.id, "grooming")

        mock_comment.assert_not_called()


# ===========================================================================
# Integration: API configuration with sync_labels
# ===========================================================================


@pytest.mark.asyncio
class TestAPIConfigSyncLabels:
    async def test_configure_with_sync_labels(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id, sync_labels=["codehive"])
        resp = await client.get(f"/api/projects/{project.id}/github/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sync_labels"] == ["codehive"]

    async def test_configure_without_sync_labels_defaults_empty(
        self, client: AsyncClient, project: Project
    ):
        """Configure without sync_labels still works (defaults to [])."""
        resp = await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={"owner": "octocat", "repo": "Hello-World", "token": "ghp_test"},
        )
        assert resp.status_code == 200

        resp = await client.get(f"/api/projects/{project.id}/github/status")
        assert resp.status_code == 200
        assert resp.json()["sync_labels"] == []

    async def test_status_returns_sync_labels(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id, sync_labels=["codehive", "auto-solve"])
        resp = await client.get(f"/api/projects/{project.id}/github/status")
        assert resp.status_code == 200
        assert resp.json()["sync_labels"] == ["codehive", "auto-solve"]


# ===========================================================================
# Integration: Webhook with label filter
# ===========================================================================


@pytest.mark.asyncio
class TestWebhookLabelFilter:
    async def test_webhook_with_matching_label_imports(self, client: AsyncClient, project: Project):
        await _configure_project(
            client, project.id, trigger_mode="manual", sync_labels=["codehive"]
        )
        payload = _gh_webhook_payload(labels=[{"name": "codehive"}])
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["action_taken"] == "imported"

    async def test_webhook_without_matching_label_filtered(
        self, client: AsyncClient, project: Project
    ):
        await _configure_project(
            client, project.id, trigger_mode="manual", sync_labels=["codehive"]
        )
        payload = _gh_webhook_payload(labels=[{"name": "bug"}])
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["action_taken"] == "filtered"

    async def test_webhook_no_sync_labels_imports_all(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id, trigger_mode="manual")
        payload = _gh_webhook_payload(labels=[{"name": "anything"}])
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["action_taken"] == "imported"

    async def test_webhook_auto_mode_with_matching_label_creates_session(
        self, client: AsyncClient, project: Project
    ):
        await _configure_project(client, project.id, trigger_mode="auto", sync_labels=["codehive"])
        payload = _gh_webhook_payload(labels=[{"name": "codehive"}], number=77)
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_taken"] == "session_created"
        assert data["session_id"] is not None
