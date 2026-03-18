"""Tests for queue_empty_action behavior in SessionScheduler."""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.schemas.session import QueueEmptyAction, SessionCreate, SessionUpdate
from codehive.core.pending_questions import list_questions
from codehive.core.scheduler import SessionScheduler
from codehive.core.task_queue import create_task, transition_task
from codehive.db.models import Base, Issue, Project
from codehive.db.models import Session as SessionModel

# ---------------------------------------------------------------------------
# Fixtures (same SQLite setup as test_scheduler.py)
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
async def issue(db_session: AsyncSession, project: Project) -> Issue:
    iss = Issue(
        project_id=project.id,
        title="Fix the login bug",
        description="Users cannot log in when using SSO.",
        status="open",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(iss)
    await db_session.commit()
    await db_session.refresh(iss)
    return iss


def _make_session(
    project: Project,
    *,
    config: dict | None = None,
    issue_id=None,
) -> SessionModel:
    return SessionModel(
        project_id=project.id,
        name="test-session",
        engine="native",
        mode="execution",
        status="executing",
        config=config or {"queue_enabled": True},
        issue_id=issue_id,
        created_at=datetime.now(timezone.utc),
    )


@pytest_asyncio.fixture
async def session(db_session: AsyncSession, project: Project) -> SessionModel:
    s = _make_session(project, config={"queue_enabled": True})
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
def mock_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


def _make_send_message_mock():
    """Create a mock for send_message that returns an async generator and tracks calls."""

    async def _empty_gen(*args, **kwargs):
        return
        yield  # pragma: no cover

    mock = MagicMock(side_effect=_empty_gen)
    return mock


@pytest_asyncio.fixture
def mock_engine() -> AsyncMock:
    engine = AsyncMock()
    engine.start_task = AsyncMock()
    # send_message must be a sync callable returning an async iterator
    engine.send_message = _make_send_message_mock()
    return engine


@pytest_asyncio.fixture
def scheduler(mock_event_bus: AsyncMock, mock_engine: AsyncMock) -> SessionScheduler:
    return SessionScheduler(
        db_session_factory=None,
        event_bus=mock_event_bus,
        engine=mock_engine,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event_types(mock_bus: AsyncMock) -> list[str]:
    return [c.args[2] for c in mock_bus.publish.call_args_list]


def _event_data(mock_bus: AsyncMock, event_type: str) -> dict | None:
    for c in mock_bus.publish.call_args_list:
        if c.args[2] == event_type:
            return c.args[3]
    return None


async def _complete_only_task(db_session, session, scheduler):
    """Create a single task, run it to done, then call on_task_completed."""
    task = await create_task(db_session, session_id=session.id, title="Only task")
    await transition_task(db_session, task.id, "running")
    await transition_task(db_session, task.id, "done")
    await scheduler.on_task_completed(session.id, task.id, db=db_session)


# ---------------------------------------------------------------------------
# Unit: stop behavior (default / backward compatibility)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestQueueEmptyStop:
    async def test_no_action_in_config_goes_idle(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
        mock_engine: AsyncMock,
    ):
        """Queue empties with no queue_empty_action in config -- session goes idle."""
        await _complete_only_task(db_session, session, scheduler)

        await db_session.refresh(session)
        assert session.status == "idle"
        mock_engine.start_task.assert_not_called()

    async def test_explicit_stop_goes_idle(
        self,
        db_session: AsyncSession,
        project: Project,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
        mock_engine: AsyncMock,
    ):
        """Queue empties with queue_empty_action=='stop' -- session goes idle."""
        s = _make_session(project, config={"queue_enabled": True, "queue_empty_action": "stop"})
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        task = await create_task(db_session, session_id=s.id, title="T1")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "done")
        await scheduler.on_task_completed(s.id, task.id, db=db_session)

        await db_session.refresh(s)
        assert s.status == "idle"
        mock_engine.start_task.assert_not_called()

    async def test_stop_emits_status_changed_idle(
        self,
        db_session: AsyncSession,
        session: SessionModel,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
    ):
        """Verify session.status_changed event with status idle is emitted."""
        await _complete_only_task(db_session, session, scheduler)

        data = _event_data(mock_event_bus, "session.status_changed")
        assert data is not None
        assert data["status"] == "idle"


# ---------------------------------------------------------------------------
# Unit: ask behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestQueueEmptyAsk:
    async def test_ask_creates_pending_question(
        self,
        db_session: AsyncSession,
        project: Project,
        scheduler: SessionScheduler,
        mock_engine: AsyncMock,
    ):
        """Queue empties with queue_empty_action=='ask' -- PendingQuestion created."""
        s = _make_session(project, config={"queue_enabled": True, "queue_empty_action": "ask"})
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        task = await create_task(db_session, session_id=s.id, title="T1")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "done")
        await scheduler.on_task_completed(s.id, task.id, db=db_session)

        questions = await list_questions(db_session, s.id)
        assert len(questions) == 1
        assert "continue" in questions[0].question.lower()

    async def test_ask_transitions_to_waiting_input(
        self,
        db_session: AsyncSession,
        project: Project,
        scheduler: SessionScheduler,
        mock_engine: AsyncMock,
    ):
        """Session transitions to waiting_input when action is ask."""
        s = _make_session(project, config={"queue_enabled": True, "queue_empty_action": "ask"})
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        task = await create_task(db_session, session_id=s.id, title="T1")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "done")
        await scheduler.on_task_completed(s.id, task.id, db=db_session)

        await db_session.refresh(s)
        assert s.status == "waiting_input"

    async def test_ask_emits_event(
        self,
        db_session: AsyncSession,
        project: Project,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
        mock_engine: AsyncMock,
    ):
        """queue_empty.ask event is emitted with question_id."""
        s = _make_session(project, config={"queue_enabled": True, "queue_empty_action": "ask"})
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        task = await create_task(db_session, session_id=s.id, title="T1")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "done")
        await scheduler.on_task_completed(s.id, task.id, db=db_session)

        assert "queue_empty.ask" in _event_types(mock_event_bus)
        data = _event_data(mock_event_bus, "queue_empty.ask")
        assert data is not None
        assert "question_id" in data

    async def test_ask_does_not_call_engine_start_task(
        self,
        db_session: AsyncSession,
        project: Project,
        scheduler: SessionScheduler,
        mock_engine: AsyncMock,
    ):
        """Engine start_task is NOT called when action is ask."""
        s = _make_session(project, config={"queue_enabled": True, "queue_empty_action": "ask"})
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        task = await create_task(db_session, session_id=s.id, title="T1")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "done")
        await scheduler.on_task_completed(s.id, task.id, db=db_session)

        mock_engine.start_task.assert_not_called()


# ---------------------------------------------------------------------------
# Unit: continue behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestQueueEmptyContinue:
    async def test_continue_calls_engine_send_message(
        self,
        db_session: AsyncSession,
        project: Project,
        issue: Issue,
        scheduler: SessionScheduler,
        mock_engine: AsyncMock,
    ):
        """When continue and issue linked, engine.send_message is called with issue title."""
        s = _make_session(
            project,
            config={"queue_enabled": True, "queue_empty_action": "continue"},
            issue_id=issue.id,
        )
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        task = await create_task(db_session, session_id=s.id, title="T1")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "done")
        await scheduler.on_task_completed(s.id, task.id, db=db_session)

        mock_engine.send_message.assert_called_once()
        call_args = mock_engine.send_message.call_args
        prompt = call_args.args[1]
        assert issue.title in prompt

    async def test_continue_emits_event_before_engine_call(
        self,
        db_session: AsyncSession,
        project: Project,
        issue: Issue,
        scheduler: SessionScheduler,
        mock_event_bus: AsyncMock,
        mock_engine: AsyncMock,
    ):
        """queue_empty.continue event is emitted with issue_id."""
        s = _make_session(
            project,
            config={"queue_enabled": True, "queue_empty_action": "continue"},
            issue_id=issue.id,
        )
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        task = await create_task(db_session, session_id=s.id, title="T1")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "done")
        await scheduler.on_task_completed(s.id, task.id, db=db_session)

        assert "queue_empty.continue" in _event_types(mock_event_bus)
        data = _event_data(mock_event_bus, "queue_empty.continue")
        assert data is not None
        assert data["issue_id"] == str(issue.id)

    async def test_continue_no_new_tasks_goes_idle(
        self,
        db_session: AsyncSession,
        project: Project,
        issue: Issue,
        scheduler: SessionScheduler,
        mock_engine: AsyncMock,
    ):
        """If engine produces no new tasks, session goes idle."""
        s = _make_session(
            project,
            config={"queue_enabled": True, "queue_empty_action": "continue"},
            issue_id=issue.id,
        )
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        task = await create_task(db_session, session_id=s.id, title="T1")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "done")
        await scheduler.on_task_completed(s.id, task.id, db=db_session)

        await db_session.refresh(s)
        assert s.status == "idle"

    async def test_continue_with_new_tasks_starts_next(
        self,
        db_session: AsyncSession,
        project: Project,
        issue: Issue,
        scheduler: SessionScheduler,
        mock_engine: AsyncMock,
        mock_event_bus: AsyncMock,
    ):
        """If engine produces new tasks, scheduler picks up the next one."""
        s = _make_session(
            project,
            config={"queue_enabled": True, "queue_empty_action": "continue"},
            issue_id=issue.id,
        )
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        # The engine's send_message will create a new task as a side effect
        async def _create_task_gen(*args, **kwargs):
            await create_task(db_session, session_id=s.id, title="Generated task")
            return
            yield  # pragma: no cover

        mock_engine.send_message = MagicMock(side_effect=_create_task_gen)

        task = await create_task(db_session, session_id=s.id, title="T1")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "done")
        await scheduler.on_task_completed(s.id, task.id, db=db_session)

        await db_session.refresh(s)
        assert s.status == "executing"
        mock_engine.start_task.assert_called_once()


# ---------------------------------------------------------------------------
# Unit: continue fallback when no issue linked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestQueueEmptyContinueFallback:
    async def test_continue_no_issue_falls_back_to_stop(
        self,
        db_session: AsyncSession,
        project: Project,
        scheduler: SessionScheduler,
        mock_engine: AsyncMock,
    ):
        """continue with no issue_id falls back to stop (idle)."""
        s = _make_session(
            project,
            config={"queue_enabled": True, "queue_empty_action": "continue"},
        )
        db_session.add(s)
        await db_session.commit()
        await db_session.refresh(s)

        task = await create_task(db_session, session_id=s.id, title="T1")
        await transition_task(db_session, task.id, "running")
        await transition_task(db_session, task.id, "done")
        await scheduler.on_task_completed(s.id, task.id, db=db_session)

        await db_session.refresh(s)
        assert s.status == "idle"
        mock_engine.send_message.assert_not_called()


# ---------------------------------------------------------------------------
# Unit: Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestQueueEmptyActionValidation:
    async def test_invalid_action_rejected_on_create(self):
        """SessionCreate rejects invalid queue_empty_action."""
        with pytest.raises(ValueError, match="Invalid queue_empty_action"):
            SessionCreate(
                name="s",
                engine="native",
                mode="execution",
                config={"queue_empty_action": "invalid"},
            )

    async def test_valid_action_accepted_on_create(self):
        """SessionCreate accepts valid queue_empty_action values."""
        for action in ("stop", "continue", "ask"):
            sc = SessionCreate(
                name="s",
                engine="native",
                mode="execution",
                config={"queue_empty_action": action},
            )
            assert sc.config["queue_empty_action"] == action

    async def test_invalid_action_rejected_on_update(self):
        """SessionUpdate rejects invalid queue_empty_action."""
        with pytest.raises(ValueError, match="Invalid queue_empty_action"):
            SessionUpdate(config={"queue_empty_action": "invalid"})

    async def test_valid_action_accepted_on_update(self):
        """SessionUpdate accepts valid queue_empty_action values."""
        su = SessionUpdate(config={"queue_empty_action": "ask"})
        assert su.config["queue_empty_action"] == "ask"


# ---------------------------------------------------------------------------
# Unit: QueueEmptyAction enum
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestQueueEmptyActionEnum:
    async def test_enum_values(self):
        """QueueEmptyAction enum has the correct values."""
        assert QueueEmptyAction.values() == {"stop", "continue", "ask"}

    async def test_enum_string_values(self):
        """Enum members have expected string values."""
        assert QueueEmptyAction.stop.value == "stop"
        assert QueueEmptyAction.continue_.value == "continue"
        assert QueueEmptyAction.ask.value == "ask"
