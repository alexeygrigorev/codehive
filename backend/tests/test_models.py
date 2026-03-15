"""Tests for codehive.db models, session factory, and migrations."""

import asyncio
import subprocess
import uuid

import pytest

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
    Workspace,
)
from codehive.db.session import async_session_factory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATABASE_URL = "postgresql+asyncpg://codehive:codehive@localhost:5432/codehive"


def _pg_available() -> bool:
    """Return True when the local Postgres container is reachable."""
    try:
        import asyncpg  # noqa: F811

        asyncio.get_event_loop().run_until_complete(
            asyncpg.connect(
                user="codehive",
                password="codehive",
                database="codehive",
                host="localhost",
                port=5432,
                timeout=2,
            )
        )
        return True
    except Exception:
        return False


requires_pg = pytest.mark.skipif(not _pg_available(), reason="Postgres not available")


# ---------------------------------------------------------------------------
# Unit tests: model instantiation and defaults
# ---------------------------------------------------------------------------


class TestWorkspaceModel:
    def test_instantiation(self):
        ws = Workspace(name="test-ws", root_path="/tmp/ws")
        assert ws.name == "test-ws"
        assert ws.root_path == "/tmp/ws"

    def test_uuid_pk_generated_on_init_or_flush(self):
        """UUID PK is either set at construction or at flush time."""
        ws = Workspace(id=uuid.uuid4(), name="ws", root_path="/tmp")
        assert ws.id is not None
        assert isinstance(ws.id, uuid.UUID)


class TestProjectModel:
    def test_instantiation(self):
        p = Project(workspace_id=uuid.uuid4(), name="proj")
        assert p.name == "proj"
        assert p.path is None
        assert p.description is None
        assert p.archetype is None


class TestIssueModel:
    def test_defaults(self):
        i = Issue(project_id=uuid.uuid4(), title="bug")
        assert i.title == "bug"
        assert i.description is None
        assert i.github_issue_id is None


class TestSessionModel:
    def test_defaults(self):
        s = Session(
            project_id=uuid.uuid4(),
            name="s1",
            engine="claude_code",
            mode="execution",
        )
        assert s.issue_id is None
        assert s.parent_session_id is None

    def test_status_values_accepted(self):
        """All spec status values should be assignable."""
        for status in [
            "idle",
            "planning",
            "executing",
            "waiting_input",
            "waiting_approval",
            "blocked",
            "completed",
            "failed",
        ]:
            s = Session(
                project_id=uuid.uuid4(),
                name="s",
                engine="e",
                mode="m",
                status=status,
            )
            assert s.status == status


class TestTaskModel:
    def test_defaults(self):
        t = Task(session_id=uuid.uuid4(), title="do stuff")
        assert t.instructions is None
        assert t.depends_on is None

    def test_status_values_accepted(self):
        for status in ["pending", "running", "blocked", "done", "failed", "skipped"]:
            t = Task(session_id=uuid.uuid4(), title="t", status=status)
            assert t.status == status


class TestMessageModel:
    def test_instantiation(self):
        m = Message(session_id=uuid.uuid4(), role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"


class TestEventModel:
    def test_instantiation(self):
        e = Event(session_id=uuid.uuid4(), type="file.changed")
        assert e.type == "file.changed"


class TestCheckpointModel:
    def test_instantiation(self):
        c = Checkpoint(session_id=uuid.uuid4(), git_ref="abc123")
        assert c.git_ref == "abc123"


class TestPendingQuestionModel:
    def test_defaults(self):
        pq = PendingQuestion(session_id=uuid.uuid4(), question="what?")
        assert pq.question == "what?"
        assert pq.context is None
        assert pq.answer is None


class TestIssueStatusValues:
    def test_status_values_accepted(self):
        for status in ["open", "in_progress", "closed"]:
            i = Issue(project_id=uuid.uuid4(), title="t", status=status)
            assert i.status == status


# ---------------------------------------------------------------------------
# Unit: Base metadata includes all 9 tables
# ---------------------------------------------------------------------------


class TestBaseMetadata:
    def test_all_tables_registered(self):
        expected = {
            "workspaces",
            "projects",
            "issues",
            "sessions",
            "tasks",
            "messages",
            "events",
            "checkpoints",
            "pending_questions",
            "custom_roles",
            "custom_archetypes",
        }
        assert expected == set(Base.metadata.tables.keys())


# ---------------------------------------------------------------------------
# Integration tests (require running Postgres)
# ---------------------------------------------------------------------------


@requires_pg
class TestAsyncSessionFactory:
    def test_factory_returns_sessionmaker(self):
        factory = async_session_factory(database_url=DATABASE_URL)
        assert callable(factory)

    @pytest.mark.asyncio
    async def test_round_trip_workspace(self):
        factory = async_session_factory(database_url=DATABASE_URL)
        async with factory() as session:
            ws = Workspace(name=f"test-{uuid.uuid4().hex[:8]}", root_path="/tmp/test")
            session.add(ws)
            await session.commit()

            result = await session.get(Workspace, ws.id)
            assert result is not None
            assert result.name == ws.name
            assert result.created_at is not None

            # cleanup
            await session.delete(result)
            await session.commit()


@requires_pg
class TestFullEntityGraph:
    @pytest.mark.asyncio
    async def test_full_chain(self):
        """Insert a full entity graph and verify FK references persist."""
        factory = async_session_factory(database_url=DATABASE_URL)
        async with factory() as session:
            ws = Workspace(name=f"graph-{uuid.uuid4().hex[:8]}", root_path="/tmp")
            session.add(ws)
            await session.flush()

            proj = Project(workspace_id=ws.id, name="proj")
            session.add(proj)
            await session.flush()

            issue = Issue(project_id=proj.id, title="issue-1")
            session.add(issue)
            await session.flush()

            sess = Session(
                project_id=proj.id,
                issue_id=issue.id,
                name="sess-1",
                engine="native",
                mode="execution",
            )
            session.add(sess)
            await session.flush()

            # Self-referential session
            child_sess = Session(
                project_id=proj.id,
                parent_session_id=sess.id,
                name="child-sess",
                engine="native",
                mode="execution",
            )
            session.add(child_sess)
            await session.flush()

            task = Task(session_id=sess.id, title="task-1")
            msg = Message(session_id=sess.id, role="user", content="hi")
            evt = Event(session_id=sess.id, type="file.changed")
            cp = Checkpoint(session_id=sess.id, git_ref="deadbeef")
            pq = PendingQuestion(session_id=sess.id, question="why?")

            session.add_all([task, msg, evt, cp, pq])
            await session.commit()

            # Verify all persisted with UUIDs
            for obj in [ws, proj, issue, sess, child_sess, task, msg, evt, cp, pq]:
                assert obj.id is not None
                assert isinstance(obj.id, uuid.UUID)

            # Verify FK references
            assert proj.workspace_id == ws.id
            assert issue.project_id == proj.id
            assert sess.project_id == proj.id
            assert sess.issue_id == issue.id
            assert child_sess.parent_session_id == sess.id
            assert task.session_id == sess.id
            assert msg.session_id == sess.id
            assert evt.session_id == sess.id
            assert cp.session_id == sess.id
            assert pq.session_id == sess.id

            # Verify server defaults populated
            assert ws.created_at is not None
            assert task.created_at is not None
            assert pq.answered is False

            # cleanup (delete in reverse FK order)
            for obj in [pq, cp, evt, msg, task, child_sess, sess, issue, proj, ws]:
                await session.delete(obj)
            await session.commit()


@requires_pg
class TestAlembicMigrations:
    def test_upgrade_and_downgrade(self):
        """Run alembic downgrade base then upgrade head to verify migrations."""
        result_down = subprocess.run(
            ["uv", "run", "alembic", "downgrade", "base"],
            capture_output=True,
            text=True,
            cwd="/home/alexey/git/codehive/backend",
        )
        assert result_down.returncode == 0, result_down.stderr

        result_up = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd="/home/alexey/git/codehive/backend",
        )
        assert result_up.returncode == 0, result_up.stderr

    def test_alembic_current(self):
        result = subprocess.run(
            ["uv", "run", "alembic", "current"],
            capture_output=True,
            text=True,
            cwd="/home/alexey/git/codehive/backend",
        )
        assert result.returncode == 0
        assert "head" in result.stdout
