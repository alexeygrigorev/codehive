"""Tests for SessionScheduler: auto-next task pickup, pending questions, and event emission."""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import JSON, MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.core.pending_questions import (
    answer_question,
    create_question,
    list_questions,
)
from codehive.core.scheduler import SessionScheduler
from codehive.core.task_queue import create_task, get_task, transition_task
from codehive.db.models import Base, Project, Workspace
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


def _sqlite_compatible_metadata() -> MetaData:
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
async def session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="native",
        mode="execution",
        status="executing",
        config={"queue_enabled": True},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
def mock_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest_asyncio.fixture
def mock_engine() -> AsyncMock:
    engine = AsyncMock()
    engine.start_task = AsyncMock()
    return engine


@pytest_asyncio.fixture
def scheduler(mock_event_bus: AsyncMock, mock_engine: AsyncMock) -> SessionScheduler:
    return SessionScheduler(
        db_session_factory=None,  # Not used directly in tests
        event_bus=mock_event_bus,
        engine=mock_engine,
    )


# ---------------------------------------------------------------------------
# Unit tests: Auto-next task pickup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSchedulerAutoNext:
    async def test_complete_task_auto_starts_next(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
        mock_engine: AsyncMock,
    ):
        """Complete a task when queue_enabled=True and another pending task exists."""
        task1 = await create_task(db_session, session_id=session.id, title="Task 1")
        task2 = await create_task(db_session, session_id=session.id, title="Task 2")

        # task1 is running and completes
        await transition_task(db_session, task1.id, "running")
        await transition_task(db_session, task1.id, "done")

        await scheduler.on_task_completed(session.id, task1.id, db=db_session)

        # task2 should now be running
        updated_task2 = await get_task(db_session, task2.id)
        assert updated_task2.status == "running"

        # Session should be executing
        await db_session.refresh(session)
        assert session.status == "executing"

        # Engine should have been called
        mock_engine.start_task.assert_called_once_with(session.id, task2.id, db=db_session)

    async def test_complete_task_no_pending_transitions_idle(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
        mock_engine: AsyncMock,
    ):
        """Complete a task when no pending tasks remain: session goes idle."""
        task1 = await create_task(db_session, session_id=session.id, title="Task 1")
        await transition_task(db_session, task1.id, "running")
        await transition_task(db_session, task1.id, "done")

        await scheduler.on_task_completed(session.id, task1.id, db=db_session)

        await db_session.refresh(session)
        assert session.status == "idle"

        # Engine should NOT have been called
        mock_engine.start_task.assert_not_called()

    async def test_complete_task_queue_disabled(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
        mock_engine: AsyncMock,
    ):
        """Complete a task when queue_enabled=False: no auto-pickup, session goes idle."""
        session.config = {"queue_enabled": False}
        await db_session.commit()
        await db_session.refresh(session)

        task1 = await create_task(db_session, session_id=session.id, title="Task 1")
        task2 = await create_task(db_session, session_id=session.id, title="Task 2")
        await transition_task(db_session, task1.id, "running")
        await transition_task(db_session, task1.id, "done")

        await scheduler.on_task_completed(session.id, task1.id, db=db_session)

        await db_session.refresh(session)
        assert session.status == "idle"

        # task2 should still be pending
        updated_task2 = await get_task(db_session, task2.id)
        assert updated_task2.status == "pending"

        mock_engine.start_task.assert_not_called()

    async def test_complete_task_skips_unmet_dependency(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
        mock_engine: AsyncMock,
    ):
        """When next pending task has unmet deps, scheduler picks the correct actionable task."""
        task1 = await create_task(db_session, session_id=session.id, title="Dep task", priority=1)
        # task2 depends on task1 (which won't be done yet)
        await create_task(
            db_session,
            session_id=session.id,
            title="Blocked by dep",
            priority=10,
            depends_on=task1.id,
        )
        task_free = await create_task(
            db_session, session_id=session.id, title="Free task", priority=5
        )

        # Mark task1 as running (not done), so task_blocked is still blocked
        await transition_task(db_session, task1.id, "running")

        # Some other task completes (simulate with a dummy)
        dummy = await create_task(db_session, session_id=session.id, title="Dummy", priority=0)
        await transition_task(db_session, dummy.id, "running")
        await transition_task(db_session, dummy.id, "done")

        await scheduler.on_task_completed(session.id, dummy.id, db=db_session)

        # task_free should have been picked (task_blocked has unmet dep)
        updated_free = await get_task(db_session, task_free.id)
        assert updated_free.status == "running"

        mock_engine.start_task.assert_called_once_with(session.id, task_free.id, db=db_session)

    async def test_engine_start_task_called_with_correct_args(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_engine: AsyncMock,
    ):
        """Verify engine.start_task is called with the correct task_id."""
        task1 = await create_task(db_session, session_id=session.id, title="T1")
        task2 = await create_task(db_session, session_id=session.id, title="T2")
        await transition_task(db_session, task1.id, "running")
        await transition_task(db_session, task1.id, "done")

        await scheduler.on_task_completed(session.id, task1.id, db=db_session)

        mock_engine.start_task.assert_called_once_with(session.id, task2.id, db=db_session)


# ---------------------------------------------------------------------------
# Unit tests: Pending questions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSchedulerPendingQuestions:
    async def test_question_asked_tasks_remain(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_engine: AsyncMock,
    ):
        """Question asked when tasks remain: PQ created, next task started, session stays executing."""
        task1 = await create_task(db_session, session_id=session.id, title="Task 1")

        await scheduler.on_question_asked(session.id, "Which DB?", "context info", db=db_session)

        # Question should be created
        questions = await list_questions(db_session, session.id)
        assert len(questions) == 1
        assert questions[0].question == "Which DB?"
        assert questions[0].answered is False

        # Task should be running
        updated_task = await get_task(db_session, task1.id)
        assert updated_task.status == "running"

        # Session should stay executing
        await db_session.refresh(session)
        assert session.status == "executing"

    async def test_question_asked_no_tasks_remain(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_engine: AsyncMock,
    ):
        """Question asked when no tasks remain: session transitions to waiting_input."""
        await scheduler.on_question_asked(session.id, "Which DB?", db=db_session)

        await db_session.refresh(session)
        assert session.status == "waiting_input"

        mock_engine.start_task.assert_not_called()

    async def test_answer_last_question_transitions_idle(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
    ):
        """Answering the last unanswered question when waiting_input transitions to idle."""
        session.status = "waiting_input"
        await db_session.commit()
        await db_session.refresh(session)

        pq = await create_question(db_session, session.id, "Q?")
        await answer_question(db_session, pq.id, "A!")

        await scheduler.on_question_answered(session.id, pq.id, db=db_session)

        await db_session.refresh(session)
        assert session.status == "idle"

    async def test_answer_one_of_multiple_stays_waiting(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
    ):
        """Answering one of multiple questions keeps session in waiting_input."""
        session.status = "waiting_input"
        await db_session.commit()
        await db_session.refresh(session)

        pq1 = await create_question(db_session, session.id, "Q1?")
        await create_question(db_session, session.id, "Q2?")
        await answer_question(db_session, pq1.id, "A1")

        await scheduler.on_question_answered(session.id, pq1.id, db=db_session)

        await db_session.refresh(session)
        assert session.status == "waiting_input"


# ---------------------------------------------------------------------------
# Unit tests: Event emission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSchedulerEventEmission:
    async def test_complete_and_auto_start_events(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
    ):
        """Complete a task and auto-start next: verify event order."""
        task1 = await create_task(db_session, session_id=session.id, title="T1")
        await create_task(db_session, session_id=session.id, title="T2")
        await transition_task(db_session, task1.id, "running")
        await transition_task(db_session, task1.id, "done")

        await scheduler.on_task_completed(session.id, task1.id, db=db_session)

        # Check event calls
        event_types = [c.args[2] for c in mock_event_bus.publish.call_args_list]
        assert "task.completed" in event_types
        assert "task.started" in event_types
        assert "session.status_changed" in event_types

        # task.completed should come first
        assert event_types[0] == "task.completed"

    async def test_complete_no_next_events(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
    ):
        """Complete last task: verify session.status_changed to idle is emitted."""
        task1 = await create_task(db_session, session_id=session.id, title="T1")
        await transition_task(db_session, task1.id, "running")
        await transition_task(db_session, task1.id, "done")

        await scheduler.on_task_completed(session.id, task1.id, db=db_session)

        event_types = [c.args[2] for c in mock_event_bus.publish.call_args_list]
        assert "task.completed" in event_types
        assert "session.status_changed" in event_types

        # Find the session.status_changed event data
        for c in mock_event_bus.publish.call_args_list:
            if c.args[2] == "session.status_changed":
                assert c.args[3]["status"] == "idle"

    async def test_question_asked_event(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
    ):
        """Question asked: verify question.asked event emitted with correct data."""
        await scheduler.on_question_asked(session.id, "Which DB?", "context", db=db_session)

        event_types = [c.args[2] for c in mock_event_bus.publish.call_args_list]
        assert "question.asked" in event_types

        for c in mock_event_bus.publish.call_args_list:
            if c.args[2] == "question.asked":
                assert c.args[3]["question"] == "Which DB?"
                assert c.args[3]["context"] == "context"

    async def test_question_answered_event(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
    ):
        """Question answered: verify question.answered event emitted with the answer."""
        session.status = "waiting_input"
        await db_session.commit()

        pq = await create_question(db_session, session.id, "Q?")
        await answer_question(db_session, pq.id, "The answer")

        await scheduler.on_question_answered(session.id, pq.id, db=db_session)

        event_types = [c.args[2] for c in mock_event_bus.publish.call_args_list]
        assert "question.answered" in event_types

        for c in mock_event_bus.publish.call_args_list:
            if c.args[2] == "question.answered":
                assert c.args[3]["answer"] == "The answer"
                assert c.args[3]["question_id"] == str(pq.id)

    async def test_queue_disabled_events(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
    ):
        """queue_enabled=False: verify task.completed and session.status_changed(idle) emitted."""
        session.config = {"queue_enabled": False}
        await db_session.commit()
        await db_session.refresh(session)

        task1 = await create_task(db_session, session_id=session.id, title="T1")
        await transition_task(db_session, task1.id, "running")
        await transition_task(db_session, task1.id, "done")

        await scheduler.on_task_completed(session.id, task1.id, db=db_session)

        event_types = [c.args[2] for c in mock_event_bus.publish.call_args_list]
        assert "task.completed" in event_types
        assert "session.status_changed" in event_types
        # No task.started should be emitted
        assert "task.started" not in event_types
