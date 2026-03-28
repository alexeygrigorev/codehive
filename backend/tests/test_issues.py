"""Tests for Issue CRUD API endpoints, log entries, and core logic."""

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
from codehive.core.issues import (
    InvalidStatusTransitionError,
    IssueHasLinkedSessionsError,
    IssueNotFoundError,
    ProjectNotFoundError,
    SessionNotFoundError,
    create_issue,
    create_issue_log_entry,
    delete_issue,
    get_issue,
    link_session_to_issue,
    list_issue_log_entries,
    list_issues,
    update_issue,
)
from codehive.db.models import Base
from codehive.db.models import Session as SessionModel

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
async def project(db_session: AsyncSession):
    """Create a project for issue tests."""
    from codehive.db.models import Project

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
    """Create an async test client with the DB session overridden."""
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
# Helper to create a session in the DB
# ---------------------------------------------------------------------------


async def _create_session(db_session: AsyncSession, project_id: uuid.UUID) -> SessionModel:
    sess = SessionModel(
        project_id=project_id,
        name="test-session",
        engine="native",
        mode="auto",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(sess)
    await db_session.commit()
    await db_session.refresh(sess)
    return sess


# ---------------------------------------------------------------------------
# Unit tests: Core issue operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreCreateIssue:
    async def test_create_issue_success(self, db_session: AsyncSession, project):
        issue = await create_issue(
            db_session,
            project_id=project.id,
            title="Bug fix",
            description="Fix the bug",
        )
        assert issue.id is not None
        assert isinstance(issue.id, uuid.UUID)
        assert issue.title == "Bug fix"
        assert issue.description == "Fix the bug"
        assert issue.status == "open"
        assert issue.project_id == project.id
        assert issue.created_at is not None

    async def test_create_issue_with_new_fields(self, db_session: AsyncSession, project):
        issue = await create_issue(
            db_session,
            project_id=project.id,
            title="Feature",
            acceptance_criteria="- [ ] All tests pass",
            assigned_agent="swe",
            priority=10,
        )
        assert issue.acceptance_criteria == "- [ ] All tests pass"
        assert issue.assigned_agent == "swe"
        assert issue.priority == 10
        assert issue.updated_at is not None

    async def test_create_issue_defaults_for_new_fields(self, db_session: AsyncSession, project):
        issue = await create_issue(
            db_session,
            project_id=project.id,
            title="Minimal",
        )
        assert issue.acceptance_criteria is None
        assert issue.assigned_agent is None
        assert issue.priority == 0
        assert issue.updated_at is not None

    async def test_create_issue_nonexistent_project(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await create_issue(
                db_session,
                project_id=uuid.uuid4(),
                title="orphan",
            )


@pytest.mark.asyncio
class TestCoreListIssues:
    async def test_list_empty(self, db_session: AsyncSession, project):
        issues = await list_issues(db_session, project.id)
        assert issues == []

    async def test_list_multiple(self, db_session: AsyncSession, project):
        await create_issue(db_session, project_id=project.id, title="Issue 1")
        await create_issue(db_session, project_id=project.id, title="Issue 2")
        issues = await list_issues(db_session, project.id)
        assert len(issues) == 2

    async def test_list_with_status_filter(self, db_session: AsyncSession, project):
        issue1 = await create_issue(db_session, project_id=project.id, title="Open issue")
        issue2 = await create_issue(db_session, project_id=project.id, title="Closed issue")
        await update_issue(db_session, issue2.id, status="closed")

        open_issues = await list_issues(db_session, project.id, status="open")
        assert len(open_issues) == 1
        assert open_issues[0].id == issue1.id

    async def test_list_with_assigned_agent_filter(self, db_session: AsyncSession, project):
        await create_issue(
            db_session, project_id=project.id, title="SWE issue", assigned_agent="swe"
        )
        await create_issue(db_session, project_id=project.id, title="QA issue", assigned_agent="qa")
        swe_issues = await list_issues(db_session, project.id, assigned_agent="swe")
        assert len(swe_issues) == 1
        assert swe_issues[0].title == "SWE issue"

    async def test_list_nonexistent_project(self, db_session: AsyncSession):
        with pytest.raises(ProjectNotFoundError):
            await list_issues(db_session, uuid.uuid4())


@pytest.mark.asyncio
class TestCoreGetIssue:
    async def test_get_existing_with_sessions(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="Get me")
        found = await get_issue(db_session, issue.id)
        assert found is not None
        assert found.id == issue.id
        # sessions relationship should be loaded
        assert found.sessions == []

    async def test_get_nonexistent(self, db_session: AsyncSession):
        result = await get_issue(db_session, uuid.uuid4())
        assert result is None


@pytest.mark.asyncio
class TestCoreUpdateIssue:
    async def test_update_partial(self, db_session: AsyncSession, project):
        issue = await create_issue(
            db_session, project_id=project.id, title="Original", description="old"
        )
        updated = await update_issue(db_session, issue.id, description="new")
        assert updated.description == "new"
        assert updated.title == "Original"  # unchanged

    async def test_update_status_valid_transition(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="Status test")
        updated = await update_issue(db_session, issue.id, status="in_progress")
        assert updated.status == "in_progress"

    async def test_update_status_invalid_transition(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="Status test")
        with pytest.raises(InvalidStatusTransitionError):
            await update_issue(db_session, issue.id, status="done")

    async def test_update_assigned_agent_changes_updated_at(
        self, db_session: AsyncSession, project
    ):
        issue = await create_issue(db_session, project_id=project.id, title="Agent test")
        original_updated_at = issue.updated_at
        # Small delay not needed; _now() will produce a new timestamp
        updated = await update_issue(db_session, issue.id, assigned_agent="swe")
        assert updated.assigned_agent == "swe"
        assert updated.updated_at >= original_updated_at

    async def test_update_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(IssueNotFoundError):
            await update_issue(db_session, uuid.uuid4(), title="x")


@pytest.mark.asyncio
class TestCoreDeleteIssue:
    async def test_delete_success(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="Delete me")
        await delete_issue(db_session, issue.id)
        assert await get_issue(db_session, issue.id) is None

    async def test_delete_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(IssueNotFoundError):
            await delete_issue(db_session, uuid.uuid4())

    async def test_delete_with_linked_sessions(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="Has sessions")
        sess = await _create_session(db_session, project.id)
        sess.issue_id = issue.id
        await db_session.commit()

        with pytest.raises(IssueHasLinkedSessionsError):
            await delete_issue(db_session, issue.id)


@pytest.mark.asyncio
class TestCoreLinkSession:
    async def test_link_session_success(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="Link test")
        sess = await _create_session(db_session, project.id)

        result = await link_session_to_issue(db_session, issue.id, sess.id)
        assert result.issue_id == issue.id

    async def test_link_nonexistent_issue(self, db_session: AsyncSession, project):
        sess = await _create_session(db_session, project.id)
        with pytest.raises(IssueNotFoundError):
            await link_session_to_issue(db_session, uuid.uuid4(), sess.id)

    async def test_link_nonexistent_session(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="Link test")
        with pytest.raises(SessionNotFoundError):
            await link_session_to_issue(db_session, issue.id, uuid.uuid4())


# ---------------------------------------------------------------------------
# Unit tests: Issue log entry operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreIssueLogEntries:
    async def test_create_log_entry(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="Log test")
        entry = await create_issue_log_entry(
            db_session, issue_id=issue.id, agent_role="swe", content="Started work"
        )
        assert entry.id is not None
        assert entry.issue_id == issue.id
        assert entry.agent_role == "swe"
        assert entry.content == "Started work"
        assert entry.created_at is not None

    async def test_create_log_entry_nonexistent_issue(self, db_session: AsyncSession):
        with pytest.raises(IssueNotFoundError):
            await create_issue_log_entry(
                db_session,
                issue_id=uuid.uuid4(),
                agent_role="swe",
                content="orphan",
            )

    async def test_list_log_entries_empty(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="Empty logs")
        entries = await list_issue_log_entries(db_session, issue.id)
        assert entries == []

    async def test_list_log_entries_chronological(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="Multi logs")
        await create_issue_log_entry(
            db_session, issue_id=issue.id, agent_role="swe", content="First"
        )
        await create_issue_log_entry(
            db_session, issue_id=issue.id, agent_role="qa", content="Second"
        )
        await create_issue_log_entry(
            db_session, issue_id=issue.id, agent_role="pm", content="Third"
        )
        entries = await list_issue_log_entries(db_session, issue.id)
        assert len(entries) == 3
        assert entries[0].content == "First"
        assert entries[1].content == "Second"
        assert entries[2].content == "Third"

    async def test_list_log_entries_nonexistent_issue(self, db_session: AsyncSession):
        with pytest.raises(IssueNotFoundError):
            await list_issue_log_entries(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Unit tests: Status transition validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreStatusTransitions:
    async def test_open_to_groomed(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="T")
        updated = await update_issue(db_session, issue.id, status="groomed")
        assert updated.status == "groomed"

    async def test_open_to_in_progress(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="T")
        updated = await update_issue(db_session, issue.id, status="in_progress")
        assert updated.status == "in_progress"

    async def test_open_to_closed(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="T")
        updated = await update_issue(db_session, issue.id, status="closed")
        assert updated.status == "closed"

    async def test_open_to_done_invalid(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="T")
        with pytest.raises(InvalidStatusTransitionError):
            await update_issue(db_session, issue.id, status="done")

    async def test_in_progress_to_done(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="T")
        await update_issue(db_session, issue.id, status="in_progress")
        updated = await update_issue(db_session, issue.id, status="done")
        assert updated.status == "done"

    async def test_done_to_open_reopen(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="T")
        await update_issue(db_session, issue.id, status="in_progress")
        await update_issue(db_session, issue.id, status="done")
        updated = await update_issue(db_session, issue.id, status="open")
        assert updated.status == "open"

    async def test_closed_to_open_reopen(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="T")
        await update_issue(db_session, issue.id, status="closed")
        updated = await update_issue(db_session, issue.id, status="open")
        assert updated.status == "open"

    async def test_closed_to_in_progress_invalid(self, db_session: AsyncSession, project):
        issue = await create_issue(db_session, project_id=project.id, title="T")
        await update_issue(db_session, issue.id, status="closed")
        with pytest.raises(InvalidStatusTransitionError):
            await update_issue(db_session, issue.id, status="in_progress")


# ---------------------------------------------------------------------------
# Integration tests: API endpoints via AsyncClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateIssueEndpoint:
    async def test_create_201(self, client: AsyncClient, project):
        resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Bug"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Bug"
        assert data["status"] == "open"
        assert data["project_id"] == str(project.id)
        assert data["priority"] == 0
        assert data["acceptance_criteria"] is None
        assert data["assigned_agent"] is None
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_with_all_new_fields(self, client: AsyncClient, project):
        resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={
                "title": "Full",
                "description": "desc",
                "acceptance_criteria": "- [ ] done",
                "assigned_agent": "swe",
                "priority": 5,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["acceptance_criteria"] == "- [ ] done"
        assert data["assigned_agent"] == "swe"
        assert data["priority"] == 5

    async def test_create_with_description(self, client: AsyncClient, project):
        resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Bug", "description": "Details here"},
        )
        assert resp.status_code == 201
        assert resp.json()["description"] == "Details here"

    async def test_create_missing_title_422(self, client: AsyncClient, project):
        resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={},
        )
        assert resp.status_code == 422

    async def test_create_bad_project_404(self, client: AsyncClient):
        resp = await client.post(
            f"/api/projects/{uuid.uuid4()}/issues",
            json={"title": "orphan"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestListIssuesEndpoint:
    async def test_list_empty_200(self, client: AsyncClient, project):
        resp = await client.get(f"/api/projects/{project.id}/issues")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_issues(self, client: AsyncClient, project):
        await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Issue 1"},
        )
        await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Issue 2"},
        )
        resp = await client.get(f"/api/projects/{project.id}/issues")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_list_with_status_filter(self, client: AsyncClient, project):
        # Create two issues
        await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Open one"},
        )
        r2 = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Close me"},
        )
        issue2_id = r2.json()["id"]
        # Close the second issue
        await client.patch(f"/api/issues/{issue2_id}", json={"status": "closed"})

        resp = await client.get(f"/api/projects/{project.id}/issues?status=open")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Open one"

    async def test_list_with_assigned_agent_filter(self, client: AsyncClient, project):
        await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "SWE task", "assigned_agent": "swe"},
        )
        await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "QA task", "assigned_agent": "qa"},
        )
        resp = await client.get(f"/api/projects/{project.id}/issues?assigned_agent=swe")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "SWE task"

    async def test_list_with_both_filters(self, client: AsyncClient, project):
        await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "SWE open", "assigned_agent": "swe"},
        )
        r2 = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "SWE in_progress", "assigned_agent": "swe"},
        )
        issue2_id = r2.json()["id"]
        await client.patch(f"/api/issues/{issue2_id}", json={"status": "in_progress"})

        resp = await client.get(
            f"/api/projects/{project.id}/issues?status=in_progress&assigned_agent=swe"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "SWE in_progress"

    async def test_list_bad_project_404(self, client: AsyncClient):
        resp = await client.get(f"/api/projects/{uuid.uuid4()}/issues")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestGetIssueEndpoint:
    async def test_get_200_with_sessions_and_logs(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Get me"},
        )
        issue_id = create_resp.json()["id"]
        resp = await client.get(f"/api/issues/{issue_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Get me"
        assert "sessions" in data
        assert data["sessions"] == []
        assert "logs" in data
        assert data["logs"] == []

    async def test_get_includes_logs(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "With logs"},
        )
        issue_id = create_resp.json()["id"]
        # Add a log entry
        await client.post(
            f"/api/issues/{issue_id}/logs",
            json={"agent_role": "swe", "content": "did stuff"},
        )
        resp = await client.get(f"/api/issues/{issue_id}")
        data = resp.json()
        assert len(data["logs"]) == 1
        assert data["logs"][0]["agent_role"] == "swe"
        assert data["logs"][0]["content"] == "did stuff"

    async def test_get_404(self, client: AsyncClient):
        resp = await client.get(f"/api/issues/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUpdateIssueEndpoint:
    async def test_patch_status_200(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Patch me"},
        )
        issue_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/issues/{issue_id}",
            json={"status": "closed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    async def test_patch_status_valid_transition(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Transition"},
        )
        issue_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/issues/{issue_id}",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    async def test_patch_status_invalid_transition_409(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Bad transition"},
        )
        issue_id = create_resp.json()["id"]
        # open -> done is invalid
        resp = await client.patch(
            f"/api/issues/{issue_id}",
            json={"status": "done"},
        )
        assert resp.status_code == 409

    async def test_patch_assigned_agent_updates_updated_at(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Agent test"},
        )
        data = create_resp.json()
        issue_id = data["id"]
        original_updated_at = data["updated_at"]

        resp = await client.patch(
            f"/api/issues/{issue_id}",
            json={"assigned_agent": "swe"},
        )
        assert resp.status_code == 200
        assert resp.json()["assigned_agent"] == "swe"
        assert resp.json()["updated_at"] >= original_updated_at

    async def test_patch_partial_fields(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Original", "description": "old"},
        )
        issue_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/issues/{issue_id}",
            json={"description": "updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "updated"
        assert resp.json()["title"] == "Original"  # unchanged

    async def test_patch_404(self, client: AsyncClient):
        resp = await client.patch(
            f"/api/issues/{uuid.uuid4()}",
            json={"status": "closed"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDeleteIssueEndpoint:
    async def test_delete_204_then_404(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Delete me"},
        )
        issue_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/issues/{issue_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/issues/{issue_id}")
        assert resp.status_code == 404

    async def test_delete_404(self, client: AsyncClient):
        resp = await client.delete(f"/api/issues/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_delete_with_linked_sessions_409(
        self, client: AsyncClient, project, db_session: AsyncSession
    ):
        # Create issue via API
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Has sessions"},
        )
        issue_id = create_resp.json()["id"]

        # Create a session and link it directly in DB
        sess = await _create_session(db_session, project.id)
        sess.issue_id = uuid.UUID(issue_id)
        await db_session.commit()

        resp = await client.delete(f"/api/issues/{issue_id}")
        assert resp.status_code == 409


@pytest.mark.asyncio
class TestLinkSessionEndpoint:
    async def test_link_session_200(self, client: AsyncClient, project, db_session: AsyncSession):
        # Create issue via API
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Link test"},
        )
        issue_id = create_resp.json()["id"]

        # Create session in DB
        sess = await _create_session(db_session, project.id)

        resp = await client.post(f"/api/issues/{issue_id}/link-session/{sess.id}")
        assert resp.status_code == 200
        assert resp.json()["issue_id"] == issue_id

    async def test_link_bad_issue_404(self, client: AsyncClient, project, db_session: AsyncSession):
        sess = await _create_session(db_session, project.id)
        resp = await client.post(f"/api/issues/{uuid.uuid4()}/link-session/{sess.id}")
        assert resp.status_code == 404

    async def test_link_bad_session_404(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Link test"},
        )
        issue_id = create_resp.json()["id"]
        resp = await client.post(f"/api/issues/{issue_id}/link-session/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration tests: Log entry API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLogEntryEndpoints:
    async def test_create_log_entry_201(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Log test"},
        )
        issue_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/issues/{issue_id}/logs",
            json={"agent_role": "swe", "content": "Started implementation"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent_role"] == "swe"
        assert data["content"] == "Started implementation"
        assert data["issue_id"] == issue_id
        assert "id" in data
        assert "created_at" in data

    async def test_create_log_entry_nonexistent_issue_404(self, client: AsyncClient):
        resp = await client.post(
            f"/api/issues/{uuid.uuid4()}/logs",
            json={"agent_role": "swe", "content": "orphan"},
        )
        assert resp.status_code == 404

    async def test_list_log_entries_chronological(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Multi logs"},
        )
        issue_id = create_resp.json()["id"]

        await client.post(
            f"/api/issues/{issue_id}/logs",
            json={"agent_role": "swe", "content": "First"},
        )
        await client.post(
            f"/api/issues/{issue_id}/logs",
            json={"agent_role": "qa", "content": "Second"},
        )
        await client.post(
            f"/api/issues/{issue_id}/logs",
            json={"agent_role": "pm", "content": "Third"},
        )

        resp = await client.get(f"/api/issues/{issue_id}/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["content"] == "First"
        assert data[1]["content"] == "Second"
        assert data[2]["content"] == "Third"

    async def test_list_log_entries_nonexistent_issue_404(self, client: AsyncClient):
        resp = await client.get(f"/api/issues/{uuid.uuid4()}/logs")
        assert resp.status_code == 404

    async def test_list_log_entries_empty(self, client: AsyncClient, project):
        create_resp = await client.post(
            f"/api/projects/{project.id}/issues",
            json={"title": "Empty"},
        )
        issue_id = create_resp.json()["id"]
        resp = await client.get(f"/api/issues/{issue_id}/logs")
        assert resp.status_code == 200
        assert resp.json() == []
