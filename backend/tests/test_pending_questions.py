"""Tests for Pending Questions CRUD and API endpoints."""

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
from codehive.core.pending_questions import (
    QuestionAlreadyAnsweredError,
    QuestionNotFoundError,
    SessionNotFoundError,
    answer_question,
    create_question,
    get_question,
    list_questions,
)
from codehive.db.models import Base, Project
from codehive.db.models import Session as SessionModel

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
async def session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="native",
        mode="execution",
        status="idle",
        config={},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


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
# Unit tests: Core pending questions CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreCreateQuestion:
    async def test_create_question_success(self, db_session: AsyncSession, session: SessionModel):
        pq = await create_question(db_session, session.id, "What framework?")
        assert pq.id is not None
        assert isinstance(pq.id, uuid.UUID)
        assert pq.question == "What framework?"
        assert pq.answered is False
        assert pq.answer is None
        assert pq.context is None
        assert pq.session_id == session.id
        assert pq.created_at is not None

    async def test_create_question_with_context(
        self, db_session: AsyncSession, session: SessionModel
    ):
        pq = await create_question(
            db_session, session.id, "Which DB?", "Choosing between Postgres and MySQL"
        )
        assert pq.question == "Which DB?"
        assert pq.context == "Choosing between Postgres and MySQL"

    async def test_create_question_nonexistent_session(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await create_question(db_session, uuid.uuid4(), "orphan question")


@pytest.mark.asyncio
class TestCoreListQuestions:
    async def test_list_ordered_by_created_at(
        self, db_session: AsyncSession, session: SessionModel
    ):
        q1 = await create_question(db_session, session.id, "First?")
        q2 = await create_question(db_session, session.id, "Second?")
        questions = await list_questions(db_session, session.id)
        assert len(questions) == 2
        assert questions[0].id == q1.id
        assert questions[1].id == q2.id

    async def test_list_filter_answered_true(self, db_session: AsyncSession, session: SessionModel):
        await create_question(db_session, session.id, "Unanswered?")
        q2 = await create_question(db_session, session.id, "Answered?")
        await answer_question(db_session, q2.id, "Yes")
        questions = await list_questions(db_session, session.id, answered=True)
        assert len(questions) == 1
        assert questions[0].answered is True

    async def test_list_filter_answered_false(
        self, db_session: AsyncSession, session: SessionModel
    ):
        q1 = await create_question(db_session, session.id, "Unanswered?")
        q2 = await create_question(db_session, session.id, "Answered?")
        await answer_question(db_session, q2.id, "Yes")
        questions = await list_questions(db_session, session.id, answered=False)
        assert len(questions) == 1
        assert questions[0].id == q1.id

    async def test_list_nonexistent_session(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await list_questions(db_session, uuid.uuid4())


@pytest.mark.asyncio
class TestCoreAnswerQuestion:
    async def test_answer_success(self, db_session: AsyncSession, session: SessionModel):
        pq = await create_question(db_session, session.id, "Framework?")
        updated = await answer_question(db_session, pq.id, "FastAPI")
        assert updated.answered is True
        assert updated.answer == "FastAPI"

    async def test_answer_already_answered(self, db_session: AsyncSession, session: SessionModel):
        pq = await create_question(db_session, session.id, "Framework?")
        await answer_question(db_session, pq.id, "FastAPI")
        with pytest.raises(QuestionAlreadyAnsweredError):
            await answer_question(db_session, pq.id, "Django")

    async def test_answer_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(QuestionNotFoundError):
            await answer_question(db_session, uuid.uuid4(), "answer")


@pytest.mark.asyncio
class TestCoreGetQuestion:
    async def test_get_existing(self, db_session: AsyncSession, session: SessionModel):
        pq = await create_question(db_session, session.id, "Q?")
        found = await get_question(db_session, pq.id)
        assert found is not None
        assert found.id == pq.id
        assert found.question == "Q?"

    async def test_get_nonexistent(self, db_session: AsyncSession):
        result = await get_question(db_session, uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# Integration tests: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListQuestionsEndpoint:
    async def test_list_200_empty(self, client: AsyncClient, session: SessionModel):
        resp = await client.get(f"/api/sessions/{session.id}/questions")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_200_with_questions(
        self, client: AsyncClient, session: SessionModel, db_session: AsyncSession
    ):
        await create_question(db_session, session.id, "Q1?")
        await create_question(db_session, session.id, "Q2?")
        resp = await client.get(f"/api/sessions/{session.id}/questions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["question"] == "Q1?"
        assert data[1]["question"] == "Q2?"

    async def test_list_filter_answered_false(
        self, client: AsyncClient, session: SessionModel, db_session: AsyncSession
    ):
        await create_question(db_session, session.id, "Unanswered?")
        q2 = await create_question(db_session, session.id, "Answered?")
        await answer_question(db_session, q2.id, "yes")
        resp = await client.get(
            f"/api/sessions/{session.id}/questions", params={"answered": "false"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["question"] == "Unanswered?"

    async def test_list_404_nonexistent_session(self, client: AsyncClient):
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/questions")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestAnswerQuestionEndpoint:
    async def test_answer_200(
        self, client: AsyncClient, session: SessionModel, db_session: AsyncSession
    ):
        pq = await create_question(db_session, session.id, "Framework?")
        resp = await client.post(
            f"/api/sessions/{session.id}/questions/{pq.id}/answer",
            json={"answer": "FastAPI"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answered"] is True
        assert data["answer"] == "FastAPI"

    async def test_answer_409_already_answered(
        self, client: AsyncClient, session: SessionModel, db_session: AsyncSession
    ):
        pq = await create_question(db_session, session.id, "Framework?")
        await answer_question(db_session, pq.id, "FastAPI")
        resp = await client.post(
            f"/api/sessions/{session.id}/questions/{pq.id}/answer",
            json={"answer": "Django"},
        )
        assert resp.status_code == 409

    async def test_answer_404_nonexistent_question(
        self, client: AsyncClient, session: SessionModel
    ):
        resp = await client.post(
            f"/api/sessions/{session.id}/questions/{uuid.uuid4()}/answer",
            json={"answer": "test"},
        )
        assert resp.status_code == 404

    async def test_answer_404_wrong_session(
        self, client: AsyncClient, session: SessionModel, db_session: AsyncSession, project: Project
    ):
        # Create another session
        other = SessionModel(
            project_id=project.id,
            name="other",
            engine="native",
            mode="execution",
            status="idle",
            config={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(other)
        await db_session.commit()
        await db_session.refresh(other)

        pq = await create_question(db_session, other.id, "Q?")
        # Try to answer via wrong session
        resp = await client.post(
            f"/api/sessions/{session.id}/questions/{pq.id}/answer",
            json={"answer": "test"},
        )
        assert resp.status_code == 404
