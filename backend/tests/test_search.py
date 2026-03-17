"""Tests for search API endpoints and core search logic."""

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
from codehive.core.search import SessionNotFoundError, search, search_session_history
from codehive.db.models import Base, Event, Issue, Message, Project, Workspace
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
async def project2(db_session: AsyncSession, workspace: Workspace) -> Project:
    """A second project for cross-project filtering tests."""
    proj = Project(
        workspace_id=workspace.id,
        name="other-project",
        knowledge={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(proj)
    await db_session.commit()
    await db_session.refresh(proj)
    return proj


@pytest_asyncio.fixture
async def session_obj(db_session: AsyncSession, project: Project) -> SessionModel:
    sess = SessionModel(
        project_id=project.id,
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


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with the DB session overridden."""
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


async def _create_message(db: AsyncSession, session_id: uuid.UUID, content: str) -> Message:
    msg = Message(
        session_id=session_id,
        role="user",
        content=content,
        metadata_={},
        created_at=datetime.now(timezone.utc),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def _create_event(
    db: AsyncSession, session_id: uuid.UUID, event_type: str, data: dict | None = None
) -> Event:
    evt = Event(
        session_id=session_id,
        type=event_type,
        data=data or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(evt)
    await db.commit()
    await db.refresh(evt)
    return evt


async def _create_issue(
    db: AsyncSession, project_id: uuid.UUID, title: str, description: str | None = None
) -> Issue:
    issue = Issue(
        project_id=project_id,
        title=title,
        description=description,
        status="open",
        created_at=datetime.now(timezone.utc),
    )
    db.add(issue)
    await db.commit()
    await db.refresh(issue)
    return issue


async def _create_session(
    db: AsyncSession, project_id: uuid.UUID, name: str = "test-session"
) -> SessionModel:
    sess = SessionModel(
        project_id=project_id,
        name=name,
        engine="native",
        mode="auto",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


# ---------------------------------------------------------------------------
# Unit tests: Core search service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreSearch:
    async def test_search_finds_all_matching_entities(
        self, db_session: AsyncSession, project: Project, session_obj: SessionModel
    ):
        """Insert sessions, messages, issues, and events with known text; search for a keyword."""
        # Create entities all containing "alpha"
        await _create_message(db_session, session_obj.id, "The alpha protocol is ready")
        await _create_event(db_session, session_obj.id, "alpha.started")
        await _create_issue(db_session, project.id, "Alpha release", "The alpha milestone")

        # The session itself is named "test-session", not matching "alpha"
        # Create a session with "alpha" in the name
        await _create_session(db_session, project.id, name="alpha-session")

        results = await search(db_session, "alpha")
        assert results.total == 4
        types_found = {r.type for r in results.results}
        assert types_found == {"session", "message", "issue", "event"}

    async def test_search_single_message_match(
        self, db_session: AsyncSession, project: Project, session_obj: SessionModel
    ):
        """Search for a term that exists only in one message."""
        await _create_message(db_session, session_obj.id, "The unique_xyzzy_token is here")
        await _create_message(db_session, session_obj.id, "No match in this one")
        await _create_issue(db_session, project.id, "Some issue")

        results = await search(db_session, "unique_xyzzy_token")
        assert results.total == 1
        assert results.results[0].type == "message"

    async def test_search_no_matches(self, db_session: AsyncSession, project: Project):
        """Search for a term with no matches returns empty results."""
        await _create_issue(db_session, project.id, "Some issue")

        results = await search(db_session, "nonexistent_term_zzz")
        assert results.total == 0
        assert results.results == []
        assert results.has_more is False

    async def test_search_entity_type_filter(
        self, db_session: AsyncSession, project: Project, session_obj: SessionModel
    ):
        """Search with entity_type='issue' filter returns only issues."""
        await _create_message(db_session, session_obj.id, "The beta feature works")
        await _create_issue(db_session, project.id, "Beta feature tracking")

        results = await search(db_session, "beta", entity_type="issue")
        assert results.total == 1
        assert all(r.type == "issue" for r in results.results)

    async def test_search_project_filter(
        self,
        db_session: AsyncSession,
        project: Project,
        project2: Project,
    ):
        """Search with project_id returns only that project's results."""
        await _create_issue(db_session, project.id, "Gamma issue in project 1")
        await _create_issue(db_session, project2.id, "Gamma issue in project 2")

        results = await search(db_session, "gamma", project_id=project.id)
        assert results.total == 1
        assert results.results[0].project_id == project.id

    async def test_search_pagination_limit(self, db_session: AsyncSession, project: Project):
        """Search with limit=2 on 5 matching records returns 2 with has_more=True."""
        for i in range(5):
            await _create_issue(db_session, project.id, f"Delta item {i}")

        results = await search(db_session, "delta", limit=2)
        assert len(results.results) == 2
        assert results.total == 5
        assert results.has_more is True

    async def test_search_pagination_offset(self, db_session: AsyncSession, project: Project):
        """Search with offset=3, limit=2 returns correct page."""
        for i in range(5):
            await _create_issue(db_session, project.id, f"Epsilon item {i}")

        results = await search(db_session, "epsilon", limit=2, offset=3)
        assert len(results.results) == 2
        assert results.total == 5
        assert results.has_more is False  # 3 + 2 = 5 = total


# ---------------------------------------------------------------------------
# Unit tests: Session history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreSessionHistory:
    async def test_search_within_session(
        self, db_session: AsyncSession, project: Project, session_obj: SessionModel
    ):
        """Search within a session returns only that session's data."""
        await _create_message(db_session, session_obj.id, "Zeta message in session")
        await _create_event(db_session, session_obj.id, "zeta.event.fired")

        # Create another session with matching content (should NOT appear)
        other_sess = await _create_session(db_session, project.id, "other-session")
        await _create_message(db_session, other_sess.id, "Zeta message in other session")

        results = await search_session_history(db_session, session_obj.id, "zeta")
        assert results.total == 2
        types_found = {r.type for r in results.results}
        assert types_found == {"message", "event"}

    async def test_search_within_session_no_matches(
        self, db_session: AsyncSession, session_obj: SessionModel
    ):
        """Search within a session with no matching content."""
        await _create_message(db_session, session_obj.id, "Hello world")

        results = await search_session_history(db_session, session_obj.id, "nonexistent_xyz")
        assert results.total == 0
        assert results.results == []

    async def test_search_nonexistent_session(self, db_session: AsyncSession):
        """Search within a nonexistent session raises error."""
        with pytest.raises(SessionNotFoundError):
            await search_session_history(db_session, uuid.uuid4(), "test")


# ---------------------------------------------------------------------------
# Integration tests: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSearchEndpoint:
    async def test_search_200(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
        session_obj: SessionModel,
    ):
        """GET /api/search?q=keyword returns 200 with correct structure."""
        await _create_message(db_session, session_obj.id, "Theta keyword here")

        resp = await client.get("/api/search?q=theta")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert "has_more" in data
        assert isinstance(data["results"], list)
        assert data["total"] >= 1

        # Check result item structure
        item = data["results"][0]
        assert "type" in item
        assert "id" in item
        assert "snippet" in item
        assert "score" in item
        assert "created_at" in item

    async def test_search_type_filter(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
        session_obj: SessionModel,
    ):
        """GET /api/search?q=keyword&type=session returns only sessions."""
        await _create_session(db_session, project.id, "iota-session")
        await _create_message(db_session, session_obj.id, "iota message content")

        resp = await client.get("/api/search?q=iota&type=session")
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["type"] == "session" for item in data["results"])

    async def test_search_invalid_type_422(self, client: AsyncClient):
        """GET /api/search?q=keyword&type=invalid returns 422."""
        resp = await client.get("/api/search?q=test&type=invalid")
        assert resp.status_code == 422

    async def test_search_missing_q_422(self, client: AsyncClient):
        """GET /api/search (no q param) returns 422."""
        resp = await client.get("/api/search")
        assert resp.status_code == 422

    async def test_search_empty_q_422(self, client: AsyncClient):
        """GET /api/search?q= (empty q) returns 422."""
        resp = await client.get("/api/search?q=")
        assert resp.status_code == 422

    async def test_search_project_filter(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
        project2: Project,
    ):
        """GET /api/search?q=keyword&project_id=<uuid> returns only that project's results."""
        await _create_issue(db_session, project.id, "Kappa issue proj1")
        await _create_issue(db_session, project2.id, "Kappa issue proj2")

        resp = await client.get(f"/api/search?q=kappa&project_id={project.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["project_id"] == str(project.id)

    async def test_search_pagination(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
    ):
        """GET /api/search?q=keyword&limit=5&offset=0 returns at most 5 results."""
        for i in range(8):
            await _create_issue(db_session, project.id, f"Lambda item {i}")

        resp = await client.get("/api/search?q=lambda&limit=5&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 5
        assert data["total"] == 8
        assert data["has_more"] is True


@pytest.mark.asyncio
class TestSessionHistoryEndpoint:
    async def test_history_200(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        session_obj: SessionModel,
    ):
        """GET /api/sessions/{id}/history?q=keyword returns 200."""
        await _create_message(db_session, session_obj.id, "Mu keyword in message")
        await _create_event(db_session, session_obj.id, "mu.event.type")

        resp = await client.get(f"/api/sessions/{session_obj.id}/history?q=mu")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert "has_more" in data
        assert data["total"] == 2

    async def test_history_nonexistent_session_404(self, client: AsyncClient):
        """GET /api/sessions/{nonexistent}/history?q=keyword returns 404."""
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/history?q=test")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSearchEdgeCases:
    async def test_multi_word_phrase(
        self,
        db_session: AsyncSession,
        project: Project,
        session_obj: SessionModel,
    ):
        """Search for a multi-word phrase matches partial content."""
        await _create_message(db_session, session_obj.id, "The quick brown fox jumps")

        # LIKE-based search with multi-word phrase
        results = await search(db_session, "quick brown")
        assert results.total == 1

    async def test_long_query_no_error(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
    ):
        """Search with a very long query string does not cause server error."""
        long_query = "x" * 600
        resp = await client.get(f"/api/search?q={long_query}")
        assert resp.status_code == 200

    async def test_search_case_insensitive(
        self,
        db_session: AsyncSession,
        project: Project,
        session_obj: SessionModel,
    ):
        """ILIKE search is case-insensitive."""
        await _create_message(db_session, session_obj.id, "UPPERCASE OMEGA content")

        results = await search(db_session, "omega")
        assert results.total == 1

    async def test_search_issue_by_description(
        self,
        db_session: AsyncSession,
        project: Project,
    ):
        """Issues are matched by description, not just title."""
        await _create_issue(
            db_session, project.id, "Generic title", description="The sigma protocol details"
        )

        results = await search(db_session, "sigma")
        assert results.total == 1
        assert results.results[0].type == "issue"
