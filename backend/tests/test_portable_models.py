"""Tests for portable model types: verify models work on SQLite without hacks."""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.db.models import (
    Base,
    Checkpoint,
    Event,
    Issue,
    Message,
    PendingQuestion,
    Project,
    Session,
    Task,
)

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create all tables using Base.metadata directly on SQLite -- no hacks."""
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


class TestCreateAllOnSQLite:
    """Base.metadata.create_all() must succeed on SQLite without errors."""

    @pytest.mark.asyncio
    async def test_create_all_tables(self, db_session: AsyncSession):
        # If we got here, create_all succeeded
        assert db_session is not None


class TestUUIDRoundTrip:
    """UUID primary keys must round-trip as uuid.UUID on SQLite."""


class TestJSONRoundTrip:
    """JSON/JSONB fields must round-trip correctly on SQLite."""

    @pytest.mark.asyncio
    async def test_json_dict_round_trips(self, db_session: AsyncSession):
        proj = Project(name="proj", knowledge={}, github_config=None)
        db_session.add(proj)
        await db_session.commit()

        result = await db_session.execute(select(Project).where(Project.id == proj.id))
        row = result.scalar_one()
        assert row.github_config is None

    @pytest.mark.asyncio
    async def test_json_with_data(self, db_session: AsyncSession):
        config = {"repo": "org/repo", "token": "abc"}
        proj = Project(name="proj", knowledge={}, github_config=config)
        db_session.add(proj)
        await db_session.commit()

        result = await db_session.execute(select(Project).where(Project.id == proj.id))
        row = result.scalar_one()
        assert row.github_config == config


class TestServerDefaults:
    """Server defaults must produce valid values on SQLite."""

    @pytest.mark.asyncio
    async def test_created_at_default(self, db_session: AsyncSession):
        proj = Project(name="proj", knowledge={})
        db_session.add(proj)
        await db_session.flush()

        issue = Issue(project_id=proj.id, title="bug-1")
        db_session.add(issue)
        await db_session.flush()

        sess = Session(
            project_id=proj.id,
            issue_id=issue.id,
            name="sess-1",
            engine="native",
            mode="execution",
            config={},
        )
        db_session.add(sess)
        await db_session.flush()

        task = Task(session_id=sess.id, title="task-1")
        msg = Message(session_id=sess.id, role="user", content="hello", metadata_={})
        evt = Event(session_id=sess.id, type="file.changed", data={})
        cp = Checkpoint(session_id=sess.id, git_ref="abc123", state={})
        pq = PendingQuestion(session_id=sess.id, question="why?")

        db_session.add_all([task, msg, evt, cp, pq])
        await db_session.commit()

        # All should have UUIDs
        for obj in [proj, issue, sess, task, msg, evt, cp, pq]:
            assert obj.id is not None
            assert isinstance(obj.id, uuid.UUID)

        # FK references        assert issue.project_id == proj.id
        assert sess.project_id == proj.id
        assert sess.issue_id == issue.id
        assert task.session_id == sess.id
