"""Tests for GitHub webhook handler and auto-session trigger."""

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.db.models import Base, Project, Session, Workspace
from codehive.integrations.github.triggers import handle_issue_event
from codehive.integrations.github.webhook import (
    WebhookEvent,
    parse_webhook_event,
    verify_signature,
)

# ---------------------------------------------------------------------------
# Fixtures: async SQLite in-memory database
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create tables in an in-memory SQLite DB and yield an async session."""
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


@pytest_asyncio.fixture
async def project_member(
    project: Project, workspace: Workspace, client: AsyncClient, db_session: AsyncSession
) -> Project:
    """Ensure the test user is an owner of the workspace for API tests."""
    from tests.conftest import ensure_workspace_membership

    await ensure_workspace_membership(db_session, workspace.id)
    return project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = "test-secret-key"


def _sign_payload(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Compute the X-Hub-Signature-256 header value for a payload."""
    mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def _gh_webhook_payload(
    *,
    action: str = "opened",
    number: int = 42,
    title: str = "Fix login bug",
    body: str | None = "Description of the bug",
    state: str = "open",
    owner: str = "octocat",
    repo: str = "Hello-World",
) -> dict:
    """Build a GitHub issues webhook payload."""
    return {
        "action": action,
        "issue": {
            "number": number,
            "title": title,
            "body": body,
            "state": state,
            "labels": [],
        },
        "repository": {
            "name": repo,
            "owner": {"login": owner},
        },
    }


async def _configure_project(
    client: AsyncClient,
    project_id: uuid.UUID,
    *,
    owner: str = "octocat",
    repo: str = "Hello-World",
    token: str = "ghp_test123",
    webhook_secret: str | None = WEBHOOK_SECRET,
    trigger_mode: str = "manual",
) -> None:
    """Configure a project's GitHub integration via the API."""
    body: dict = {"owner": owner, "repo": repo, "token": token, "trigger_mode": trigger_mode}
    if webhook_secret is not None:
        body["webhook_secret"] = webhook_secret
    resp = await client.post(f"/api/projects/{project_id}/github/configure", json=body)
    assert resp.status_code == 200


async def _post_webhook(
    client: AsyncClient,
    payload: dict,
    *,
    event_type: str = "issues",
    secret: str | None = WEBHOOK_SECRET,
) -> "Response":  # noqa: F821
    """Post a webhook delivery to the endpoint."""
    raw = json.dumps(payload).encode("utf-8")
    headers = {"X-GitHub-Event": event_type, "Content-Type": "application/json"}
    if secret is not None:
        headers["X-Hub-Signature-256"] = _sign_payload(raw, secret)
    return await client.post("/api/webhooks/github", content=raw, headers=headers)


# ===========================================================================
# Unit: Signature verification
# ===========================================================================


class TestVerifySignature:
    def test_valid_signature(self):
        payload = b'{"action": "opened"}'
        sig = _sign_payload(payload)
        assert verify_signature(payload, sig, WEBHOOK_SECRET) is True

    def test_wrong_secret(self):
        payload = b'{"action": "opened"}'
        sig = _sign_payload(payload, "wrong-secret")
        assert verify_signature(payload, sig, WEBHOOK_SECRET) is False

    def test_malformed_signature_missing_prefix(self):
        payload = b'{"action": "opened"}'
        assert verify_signature(payload, "not-a-sha256-sig", WEBHOOK_SECRET) is False

    def test_empty_signature(self):
        payload = b'{"action": "opened"}'
        assert verify_signature(payload, "", WEBHOOK_SECRET) is False


# ===========================================================================
# Unit: Webhook event parsing
# ===========================================================================


class TestParseWebhookEvent:
    def test_issues_opened(self):
        headers = {"x-github-event": "issues"}
        body = {"action": "opened", "issue": {"number": 1}}
        event = parse_webhook_event(headers, body)
        assert event.event_type == "issues"
        assert event.action == "opened"
        assert event.payload == body

    def test_push_event(self):
        headers = {"x-github-event": "push"}
        body = {"ref": "refs/heads/main"}
        event = parse_webhook_event(headers, body)
        assert event.event_type == "push"
        assert event.action == ""

    def test_issues_closed(self):
        headers = {"x-github-event": "issues"}
        body = {"action": "closed", "issue": {"number": 5}}
        event = parse_webhook_event(headers, body)
        assert event.event_type == "issues"
        assert event.action == "closed"


# ===========================================================================
# Unit: Trigger logic
# ===========================================================================


@pytest.mark.asyncio
class TestTriggerLogic:
    async def test_manual_mode_imports_only(self, db_session: AsyncSession, project: Project):
        event = WebhookEvent(
            event_type="issues",
            action="opened",
            payload=_gh_webhook_payload()["issue"] | {"issue": _gh_webhook_payload()["issue"]},
        )
        # Fix: payload needs to have "issue" key at top level
        event = WebhookEvent(
            event_type="issues",
            action="opened",
            payload=_gh_webhook_payload(),
        )
        result = await handle_issue_event(db_session, project.id, event, "manual")
        assert result.action_taken == "imported"
        assert result.issue_id is not None
        assert result.session_id is None

    async def test_suggest_mode_returns_suggested(self, db_session: AsyncSession, project: Project):
        event = WebhookEvent(
            event_type="issues",
            action="opened",
            payload=_gh_webhook_payload(),
        )
        result = await handle_issue_event(db_session, project.id, event, "suggest")
        assert result.action_taken == "suggested"
        assert result.issue_id is not None
        assert result.session_id is None

    async def test_auto_mode_opened_creates_session(
        self, db_session: AsyncSession, project: Project
    ):
        event = WebhookEvent(
            event_type="issues",
            action="opened",
            payload=_gh_webhook_payload(number=42, title="Fix login bug"),
        )
        result = await handle_issue_event(db_session, project.id, event, "auto")
        assert result.action_taken == "session_created"
        assert result.issue_id is not None
        assert result.session_id is not None

    async def test_auto_mode_closed_no_session(self, db_session: AsyncSession, project: Project):
        event = WebhookEvent(
            event_type="issues",
            action="closed",
            payload=_gh_webhook_payload(action="closed", state="closed"),
        )
        result = await handle_issue_event(db_session, project.id, event, "auto")
        assert result.action_taken == "imported"
        assert result.session_id is None

    async def test_auto_mode_reopened_creates_session(
        self, db_session: AsyncSession, project: Project
    ):
        event = WebhookEvent(
            event_type="issues",
            action="reopened",
            payload=_gh_webhook_payload(action="reopened"),
        )
        result = await handle_issue_event(db_session, project.id, event, "auto")
        assert result.action_taken == "session_created"
        assert result.session_id is not None

    async def test_auto_mode_edited_imports_only(self, db_session: AsyncSession, project: Project):
        event = WebhookEvent(
            event_type="issues",
            action="edited",
            payload=_gh_webhook_payload(action="edited"),
        )
        result = await handle_issue_event(db_session, project.id, event, "auto")
        assert result.action_taken == "imported"
        assert result.session_id is None

    async def test_auto_session_has_correct_attributes(
        self, db_session: AsyncSession, project: Project
    ):
        event = WebhookEvent(
            event_type="issues",
            action="opened",
            payload=_gh_webhook_payload(number=42, title="Fix login bug"),
        )
        result = await handle_issue_event(db_session, project.id, event, "auto")

        session = await db_session.get(Session, result.session_id)
        assert session is not None
        assert session.name == "GH#42: Fix login bug"
        assert session.engine == "native"
        assert session.mode == "execution"
        assert session.status == "idle"
        assert session.issue_id == result.issue_id


# ===========================================================================
# Integration: Webhook API endpoint via AsyncClient
# ===========================================================================


@pytest.mark.asyncio
class TestWebhookEndpoint:
    async def test_valid_issues_opened_200(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id, trigger_mode="manual")
        payload = _gh_webhook_payload()
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_taken"] == "imported"

    async def test_invalid_signature_401(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id)
        payload = _gh_webhook_payload()
        resp = await _post_webhook(client, payload, secret="wrong-secret")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid signature"

    async def test_unknown_repo_404(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id)
        payload = _gh_webhook_payload(owner="unknown", repo="nonexistent")
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 404
        assert "No project configured" in resp.json()["detail"]

    async def test_push_event_ignored(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id)
        payload = {
            "ref": "refs/heads/main",
            "repository": {"name": "Hello-World", "owner": {"login": "octocat"}},
        }
        resp = await _post_webhook(client, payload, event_type="push")
        assert resp.status_code == 200
        assert resp.json()["action_taken"] == "ignored"

    async def test_unsupported_action_ignored(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id)
        payload = _gh_webhook_payload(action="labeled")
        # Override action in payload
        payload["action"] = "labeled"
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["action_taken"] == "ignored"

    async def test_auto_mode_creates_session(self, client: AsyncClient, project_member: Project):
        await _configure_project(client, project_member.id, trigger_mode="auto")
        payload = _gh_webhook_payload(number=99, title="Auto issue")
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_taken"] == "session_created"
        assert data["session_id"] is not None

        # Verify session is retrievable
        session_resp = await client.get(f"/api/sessions/{data['session_id']}")
        assert session_resp.status_code == 200
        session_data = session_resp.json()
        assert session_data["name"] == "GH#99: Auto issue"
        assert session_data["engine"] == "native"
        assert session_data["mode"] == "execution"
        assert session_data["status"] == "idle"
        assert session_data["issue_id"] == data["issue_id"]

    async def test_no_webhook_secret_still_processes(self, client: AsyncClient, project: Project):
        # Configure without webhook_secret
        await _configure_project(client, project.id, webhook_secret=None, trigger_mode="manual")
        payload = _gh_webhook_payload()
        # Post without signature
        raw = json.dumps(payload).encode("utf-8")
        headers = {"X-GitHub-Event": "issues", "Content-Type": "application/json"}
        resp = await client.post("/api/webhooks/github", content=raw, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["action_taken"] == "imported"

    async def test_manual_mode_no_session_created(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id, trigger_mode="manual")
        payload = _gh_webhook_payload()
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_taken"] == "imported"
        assert data["session_id"] is None

    async def test_suggest_mode(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id, trigger_mode="suggest")
        payload = _gh_webhook_payload()
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_taken"] == "suggested"
        assert data["session_id"] is None

    async def test_auto_mode_closed_no_session(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id, trigger_mode="auto")
        payload = _gh_webhook_payload(action="closed", state="closed")
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_taken"] == "imported"
        assert data["session_id"] is None

    async def test_auto_mode_reopened_creates_session(self, client: AsyncClient, project: Project):
        await _configure_project(client, project.id, trigger_mode="auto")
        payload = _gh_webhook_payload(action="reopened")
        resp = await _post_webhook(client, payload)
        assert resp.status_code == 200
        assert resp.json()["action_taken"] == "session_created"
        assert resp.json()["session_id"] is not None


# ===========================================================================
# Integration: Configuration backward compatibility
# ===========================================================================


@pytest.mark.asyncio
class TestConfigurationBackwardCompat:
    async def test_configure_without_new_fields(self, client: AsyncClient, project: Project):
        """Configure without webhook_secret or trigger_mode still works."""
        resp = await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={"owner": "octocat", "repo": "Hello-World", "token": "ghp_test"},
        )
        assert resp.status_code == 200

    async def test_configure_with_trigger_mode_auto(self, client: AsyncClient, project: Project):
        """Configure with trigger_mode: auto stores it and GET status returns it."""
        await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={
                "owner": "octocat",
                "repo": "Hello-World",
                "token": "ghp_test",
                "trigger_mode": "auto",
            },
        )
        resp = await client.get(f"/api/projects/{project.id}/github/status")
        assert resp.status_code == 200
        assert resp.json()["trigger_mode"] == "auto"

    async def test_status_default_trigger_mode(self, client: AsyncClient, project: Project):
        """Status for project configured without trigger_mode returns 'manual' as default."""
        # Configure without trigger_mode (it defaults to "manual")
        await client.post(
            f"/api/projects/{project.id}/github/configure",
            json={"owner": "octocat", "repo": "Hello-World", "token": "ghp_test"},
        )
        resp = await client.get(f"/api/projects/{project.id}/github/status")
        assert resp.status_code == 200
        assert resp.json()["trigger_mode"] == "manual"

    async def test_status_includes_trigger_mode(self, client: AsyncClient, project: Project):
        """GET status includes trigger_mode in response."""
        await _configure_project(client, project.id, trigger_mode="suggest")
        resp = await client.get(f"/api/projects/{project.id}/github/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "trigger_mode" in data
        assert data["trigger_mode"] == "suggest"


# ===========================================================================
# Integration: Webhooks router is registered
# ===========================================================================


@pytest.mark.asyncio
class TestWebhooksRouterRegistered:
    async def test_webhook_endpoint_accessible(self, client: AsyncClient):
        """The webhook endpoint responds (not a 404 from missing route)."""
        # Without any project, we should get 404 for "no project configured" not route-missing
        payload = _gh_webhook_payload()
        raw = json.dumps(payload).encode("utf-8")
        headers = {"X-GitHub-Event": "issues", "Content-Type": "application/json"}
        resp = await client.post("/api/webhooks/github", content=raw, headers=headers)
        # Should be 404 "No project configured" not 404 "Not Found" (route missing)
        assert resp.status_code == 404
        assert "No project configured" in resp.json()["detail"]
