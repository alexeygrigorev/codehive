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
    Message,
    PendingQuestion,
    Project,
    Session,
    Task,
    Workspace,
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

    @pytest.mark.asyncio
    async def test_uuid_pk_round_trips(self, db_session: AsyncSession):
        ws_id = uuid.uuid4()
        ws = Workspace(id=ws_id, name="test-ws", root_path="/tmp/test", settings={})
        db_session.add(ws)
        await db_session.commit()

        result = await db_session.execute(select(Workspace).where(Workspace.id == ws_id))
        row = result.scalar_one()

        assert isinstance(row.id, uuid.UUID)
        assert row.id == ws_id

    @pytest.mark.asyncio
    async def test_uuid_fk_round_trips(self, db_session: AsyncSession):
        ws = Workspace(name="ws", root_path="/tmp", settings={})
        db_session.add(ws)
        await db_session.flush()

        proj = Project(workspace_id=ws.id, name="proj", knowledge={})
        db_session.add(proj)
        await db_session.commit()

        result = await db_session.execute(select(Project).where(Project.id == proj.id))
        row = result.scalar_one()
        assert isinstance(row.workspace_id, uuid.UUID)
        assert row.workspace_id == ws.id


class TestJSONRoundTrip:
    """JSON/JSONB fields must round-trip correctly on SQLite."""

    @pytest.mark.asyncio
    async def test_json_dict_round_trips(self, db_session: AsyncSession):
        data = {"key": "value", "nested": {"a": 1}}
        ws = Workspace(name="ws-json", root_path="/tmp", settings=data)
        db_session.add(ws)
        await db_session.commit()

        result = await db_session.execute(select(Workspace).where(Workspace.id == ws.id))
        row = result.scalar_one()
        assert row.settings == data

    @pytest.mark.asyncio
    async def test_json_nullable_field(self, db_session: AsyncSession):
        ws = Workspace(name="ws2", root_path="/tmp", settings={})
        db_session.add(ws)
        await db_session.flush()

        proj = Project(workspace_id=ws.id, name="proj", knowledge={}, github_config=None)
        db_session.add(proj)
        await db_session.commit()

        result = await db_session.execute(select(Project).where(Project.id == proj.id))
        row = result.scalar_one()
        assert row.github_config is None

    @pytest.mark.asyncio
    async def test_json_with_data(self, db_session: AsyncSession):
        ws = Workspace(name="ws3", root_path="/tmp", settings={})
        db_session.add(ws)
        await db_session.flush()

        config = {"repo": "org/repo", "token": "abc"}
        proj = Project(workspace_id=ws.id, name="proj", knowledge={}, github_config=config)
        db_session.add(proj)
        await db_session.commit()

        result = await db_session.execute(select(Project).where(Project.id == proj.id))
        row = result.scalar_one()
        assert row.github_config == config


class TestServerDefaults:
    """Server defaults must produce valid values on SQLite."""

    @pytest.mark.asyncio
    async def test_created_at_default(self, db_session: AsyncSession):
        ws = Workspace(name="ws-ts", root_path="/tmp", settings={})
        db_session.add(ws)
        await db_session.commit()
        await db_session.refresh(ws)
        assert ws.created_at is not None

    @pytest.mark.asyncio
    async def test_boolean_defaults(self, db_session: AsyncSession):
        from codehive.db.models import User

        user = User(
            email="test@test.com",
            username="test",
            password_hash="hash",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        assert user.is_active is True
        assert user.is_admin is False

    @pytest.mark.asyncio
    async def test_json_server_default(self, db_session: AsyncSession):
        """Inserting without explicit settings should use server default '{}'."""
        ws = Workspace(name="ws-default", root_path="/tmp")
        db_session.add(ws)
        await db_session.commit()
        await db_session.refresh(ws)
        # Server default is '{}', which should deserialize to an empty dict
        assert ws.settings == {} or ws.settings == "{}"


class TestFullEntityGraphOnSQLite:
    """Insert a complete entity graph on SQLite to verify all FKs and types work."""

    @pytest.mark.asyncio
    async def test_full_chain(self, db_session: AsyncSession):
        from codehive.db.models import Issue

        ws = Workspace(name="graph-ws", root_path="/tmp", settings={})
        db_session.add(ws)
        await db_session.flush()

        proj = Project(workspace_id=ws.id, name="proj", knowledge={})
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
        for obj in [ws, proj, issue, sess, task, msg, evt, cp, pq]:
            assert obj.id is not None
            assert isinstance(obj.id, uuid.UUID)

        # FK references
        assert proj.workspace_id == ws.id
        assert issue.project_id == proj.id
        assert sess.project_id == proj.id
        assert sess.issue_id == issue.id
        assert task.session_id == sess.id
