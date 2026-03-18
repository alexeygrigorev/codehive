"""Tests for session persistence and recovery (issue #100)."""

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
from codehive.core.session import (
    InvalidStatusTransitionError,
    NoUserMessageError,
    SessionNotFoundError,
    create_session,
    mark_interrupted_sessions,
    resume_interrupted_session,
)
from codehive.db.models import Base, Message, Project
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures
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


@pytest_asyncio.fixture
async def project_member(
    project: Project, client: AsyncClient, db_session: AsyncSession
) -> Project:
    return project


# ---------------------------------------------------------------------------
# Unit: mark_interrupted_sessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMarkInterruptedSessions:
    async def test_marks_only_executing(self, db_session: AsyncSession, project: Project):
        """Only sessions with status 'executing' are marked interrupted."""
        s1 = await create_session(
            db_session, project_id=project.id, name="s1", engine="native", mode="execution"
        )
        s2 = await create_session(
            db_session, project_id=project.id, name="s2", engine="native", mode="execution"
        )
        s3 = await create_session(
            db_session, project_id=project.id, name="s3", engine="native", mode="execution"
        )

        # Set statuses
        s1.status = "executing"
        s2.status = "idle"
        s3.status = "completed"
        await db_session.commit()

        count = await mark_interrupted_sessions(db_session)
        assert count == 1

        await db_session.refresh(s1)
        await db_session.refresh(s2)
        await db_session.refresh(s3)
        assert s1.status == "interrupted"
        assert s2.status == "idle"
        assert s3.status == "completed"

    async def test_returns_zero_when_none(self, db_session: AsyncSession, project: Project):
        """Returns 0 when no sessions are in executing status."""
        await create_session(
            db_session, project_id=project.id, name="s1", engine="native", mode="execution"
        )
        count = await mark_interrupted_sessions(db_session)
        assert count == 0

    async def test_idempotent(self, db_session: AsyncSession, project: Project):
        """Calling twice returns 0 the second time."""
        s1 = await create_session(
            db_session, project_id=project.id, name="s1", engine="native", mode="execution"
        )
        s1.status = "executing"
        await db_session.commit()

        count1 = await mark_interrupted_sessions(db_session)
        assert count1 == 1

        count2 = await mark_interrupted_sessions(db_session)
        assert count2 == 0

    async def test_marks_multiple(self, db_session: AsyncSession, project: Project):
        """Multiple executing sessions are all marked."""
        s1 = await create_session(
            db_session, project_id=project.id, name="s1", engine="native", mode="execution"
        )
        s2 = await create_session(
            db_session, project_id=project.id, name="s2", engine="native", mode="execution"
        )
        s1.status = "executing"
        s2.status = "executing"
        await db_session.commit()

        count = await mark_interrupted_sessions(db_session)
        assert count == 2

        await db_session.refresh(s1)
        await db_session.refresh(s2)
        assert s1.status == "interrupted"
        assert s2.status == "interrupted"


# ---------------------------------------------------------------------------
# Unit: resume_interrupted_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestResumeInterruptedSession:
    async def test_resumes_and_returns_last_message(
        self, db_session: AsyncSession, project: Project
    ):
        """Resumes interrupted session, returns last user message."""
        session = await create_session(
            db_session, project_id=project.id, name="s", engine="native", mode="execution"
        )
        session.status = "interrupted"
        await db_session.commit()

        # Add messages
        db_session.add(
            Message(
                session_id=session.id,
                role="user",
                content="first message",
                metadata_={},
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        )
        db_session.add(
            Message(
                session_id=session.id,
                role="assistant",
                content="response",
                metadata_={},
                created_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
            )
        )
        db_session.add(
            Message(
                session_id=session.id,
                role="user",
                content="last user msg",
                metadata_={},
                created_at=datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
            )
        )
        await db_session.commit()

        result_session, last_msg = await resume_interrupted_session(db_session, session.id)
        assert result_session.status == "executing"
        assert last_msg == "last user msg"

    async def test_rejects_non_interrupted_status(self, db_session: AsyncSession, project: Project):
        """Raises InvalidStatusTransitionError for non-interrupted sessions."""
        session = await create_session(
            db_session, project_id=project.id, name="s", engine="native", mode="execution"
        )
        # status is 'idle' by default
        with pytest.raises(InvalidStatusTransitionError):
            await resume_interrupted_session(db_session, session.id)

    async def test_rejects_no_user_messages(self, db_session: AsyncSession, project: Project):
        """Raises NoUserMessageError when there are no user messages."""
        session = await create_session(
            db_session, project_id=project.id, name="s", engine="native", mode="execution"
        )
        session.status = "interrupted"
        await db_session.commit()

        with pytest.raises(NoUserMessageError):
            await resume_interrupted_session(db_session, session.id)

    async def test_not_found(self, db_session: AsyncSession):
        """Raises SessionNotFoundError for non-existent session."""
        with pytest.raises(SessionNotFoundError):
            await resume_interrupted_session(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# Unit: interrupted status validity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestInterruptedStatusValidity:
    async def test_interrupted_is_valid_status(self, db_session: AsyncSession, project: Project):
        """The 'interrupted' status can be set on a session."""
        session = await create_session(
            db_session, project_id=project.id, name="s", engine="native", mode="execution"
        )
        session.status = "interrupted"
        await db_session.commit()
        await db_session.refresh(session)
        assert session.status == "interrupted"

    async def test_interrupted_not_pausable(self, db_session: AsyncSession, project: Project):
        """'interrupted' is not in _PAUSABLE_STATUSES -- cannot pause from it."""
        from codehive.core.session import pause_session

        session = await create_session(
            db_session, project_id=project.id, name="s", engine="native", mode="execution"
        )
        session.status = "interrupted"
        await db_session.commit()

        with pytest.raises(InvalidStatusTransitionError):
            await pause_session(db_session, session.id)


# ---------------------------------------------------------------------------
# Integration: startup recovery via lifespan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStartupRecovery:
    async def test_startup_marks_executing_as_interrupted(
        self, db_session: AsyncSession, project: Project
    ):
        """Simulate startup: executing sessions become interrupted."""
        s1 = await create_session(
            db_session, project_id=project.id, name="s1", engine="native", mode="execution"
        )
        s2 = await create_session(
            db_session, project_id=project.id, name="s2", engine="native", mode="execution"
        )
        s1.status = "executing"
        s2.status = "idle"
        await db_session.commit()

        # Simulate what lifespan startup does
        count = await mark_interrupted_sessions(db_session)
        assert count == 1

        await db_session.refresh(s1)
        assert s1.status == "interrupted"

        await db_session.refresh(s2)
        assert s2.status == "idle"


# ---------------------------------------------------------------------------
# Integration: graceful shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGracefulShutdown:
    async def test_shutdown_marks_executing_as_interrupted(
        self, db_session: AsyncSession, project: Project
    ):
        """Simulate shutdown: executing sessions become interrupted."""
        s1 = await create_session(
            db_session, project_id=project.id, name="s1", engine="native", mode="execution"
        )
        s1.status = "executing"
        await db_session.commit()

        # Simulate what lifespan shutdown does
        count = await mark_interrupted_sessions(db_session)
        assert count == 1

        await db_session.refresh(s1)
        assert s1.status == "interrupted"


# ---------------------------------------------------------------------------
# Integration: resume-interrupted endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestResumeInterruptedEndpoint:
    async def test_resume_interrupted_200(
        self, client: AsyncClient, project_member: Project, db_session: AsyncSession
    ):
        """POST /api/sessions/{id}/resume-interrupted returns 200 for interrupted sessions."""
        create_resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "s", "engine": "native", "mode": "execution"},
        )
        assert create_resp.status_code == 201, create_resp.text
        session_id = create_resp.json()["id"]

        # Set status to interrupted and add a user message
        s = await db_session.get(SessionModel, uuid.UUID(session_id))
        s.status = "interrupted"
        await db_session.commit()

        db_session.add(
            Message(
                session_id=uuid.UUID(session_id),
                role="user",
                content="hello",
                metadata_={},
                created_at=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()

        resp = await client.post(f"/api/sessions/{session_id}/resume-interrupted")
        assert resp.status_code == 200
        assert resp.json()["status"] == "executing"

    async def test_resume_interrupted_409_wrong_status(
        self, client: AsyncClient, project_member: Project
    ):
        """POST /api/sessions/{id}/resume-interrupted returns 409 for non-interrupted."""
        create_resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "s", "engine": "native", "mode": "execution"},
        )
        session_id = create_resp.json()["id"]

        resp = await client.post(f"/api/sessions/{session_id}/resume-interrupted")
        assert resp.status_code == 409

    async def test_resume_interrupted_404(self, client: AsyncClient):
        """POST /api/sessions/{id}/resume-interrupted returns 404 for non-existent."""
        resp = await client.post(f"/api/sessions/{uuid.uuid4()}/resume-interrupted")
        assert resp.status_code == 404

    async def test_resume_interrupted_409_no_messages(
        self, client: AsyncClient, project_member: Project, db_session: AsyncSession
    ):
        """POST resume-interrupted returns 409 when no user messages exist."""
        create_resp = await client.post(
            f"/api/projects/{project_member.id}/sessions",
            json={"name": "s", "engine": "native", "mode": "execution"},
        )
        session_id = create_resp.json()["id"]

        s = await db_session.get(SessionModel, uuid.UUID(session_id))
        s.status = "interrupted"
        await db_session.commit()

        resp = await client.post(f"/api/sessions/{session_id}/resume-interrupted")
        assert resp.status_code == 409
