"""Tests for Checkpoint creation, listing, rollback, auto-checkpoint, and API endpoints."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.checkpoint import (
    CheckpointNotFoundError,
    SessionNotFoundError,
    create_checkpoint,
    list_checkpoints,
    rollback_checkpoint,
)
from codehive.db.models import Base, Project, Workspace
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
    """Create a workspace for tests."""
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
    """Create a project for tests."""
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
    """Create a session for checkpoint tests."""
    s = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="native",
        mode="execution",
        status="executing",
        config={"project_root": "/tmp/test-repo"},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
def mock_git_ops() -> AsyncMock:
    """Create a mock GitOps that returns a fake SHA on commit."""
    git_ops = AsyncMock()
    git_ops.commit.return_value = "abc123def456"
    git_ops.checkout.return_value = None
    return git_ops


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
# Unit tests: core/checkpoint.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateCheckpoint:
    async def test_create_checkpoint_success(
        self, db_session: AsyncSession, session: SessionModel, mock_git_ops: AsyncMock
    ):
        checkpoint = await create_checkpoint(
            db_session,
            mock_git_ops,
            session_id=session.id,
            label="manual checkpoint",
        )
        assert checkpoint.id is not None
        assert isinstance(checkpoint.id, uuid.UUID)
        assert checkpoint.session_id == session.id
        assert checkpoint.git_ref == "abc123def456"
        assert checkpoint.state["status"] == "executing"
        assert checkpoint.state["mode"] == "execution"
        assert checkpoint.state["config"] == {"project_root": "/tmp/test-repo"}
        assert checkpoint.state["label"] == "manual checkpoint"
        assert checkpoint.created_at is not None
        mock_git_ops.commit.assert_awaited_once_with("checkpoint: manual checkpoint")

    async def test_create_checkpoint_no_label(
        self, db_session: AsyncSession, session: SessionModel, mock_git_ops: AsyncMock
    ):
        checkpoint = await create_checkpoint(
            db_session,
            mock_git_ops,
            session_id=session.id,
        )
        assert checkpoint.git_ref == "abc123def456"
        assert "label" not in checkpoint.state
        mock_git_ops.commit.assert_awaited_once_with("checkpoint")

    async def test_create_checkpoint_nonexistent_session(
        self, db_session: AsyncSession, mock_git_ops: AsyncMock
    ):
        with pytest.raises(SessionNotFoundError):
            await create_checkpoint(
                db_session,
                mock_git_ops,
                session_id=uuid.uuid4(),
            )


@pytest.mark.asyncio
class TestListCheckpoints:
    async def test_list_empty(self, db_session: AsyncSession, session: SessionModel):
        checkpoints = await list_checkpoints(db_session, session.id)
        assert checkpoints == []

    async def test_list_ordered_desc(
        self, db_session: AsyncSession, session: SessionModel, mock_git_ops: AsyncMock
    ):
        # Create two checkpoints
        mock_git_ops.commit.return_value = "sha1"
        cp1 = await create_checkpoint(
            db_session, mock_git_ops, session_id=session.id, label="first"
        )
        mock_git_ops.commit.return_value = "sha2"
        cp2 = await create_checkpoint(
            db_session, mock_git_ops, session_id=session.id, label="second"
        )

        checkpoints = await list_checkpoints(db_session, session.id)
        assert len(checkpoints) == 2
        # Most recent first
        assert checkpoints[0].id == cp2.id
        assert checkpoints[1].id == cp1.id

    async def test_list_nonexistent_session(self, db_session: AsyncSession):
        with pytest.raises(SessionNotFoundError):
            await list_checkpoints(db_session, uuid.uuid4())


@pytest.mark.asyncio
class TestRollbackCheckpoint:
    async def test_rollback_restores_session_state(
        self, db_session: AsyncSession, session: SessionModel, mock_git_ops: AsyncMock
    ):
        # Create checkpoint with current state
        checkpoint = await create_checkpoint(
            db_session, mock_git_ops, session_id=session.id, label="before change"
        )

        # Modify session state
        session.status = "failed"
        session.mode = "review"
        session.config = {"changed": True}
        await db_session.commit()

        # Rollback
        restored = await rollback_checkpoint(db_session, mock_git_ops, checkpoint_id=checkpoint.id)
        assert restored.status == "executing"
        assert restored.mode == "execution"
        assert restored.config == {"project_root": "/tmp/test-repo"}
        mock_git_ops.checkout.assert_awaited_once_with("abc123def456")

    async def test_rollback_nonexistent_checkpoint(
        self, db_session: AsyncSession, mock_git_ops: AsyncMock
    ):
        with pytest.raises(CheckpointNotFoundError):
            await rollback_checkpoint(db_session, mock_git_ops, checkpoint_id=uuid.uuid4())

    async def test_rollback_calls_git_checkout(
        self, db_session: AsyncSession, session: SessionModel, mock_git_ops: AsyncMock
    ):
        mock_git_ops.commit.return_value = "deadbeef"
        checkpoint = await create_checkpoint(db_session, mock_git_ops, session_id=session.id)

        await rollback_checkpoint(db_session, mock_git_ops, checkpoint_id=checkpoint.id)
        mock_git_ops.checkout.assert_awaited_once_with("deadbeef")


# ---------------------------------------------------------------------------
# Integration tests: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateCheckpointEndpoint:
    async def test_create_201(
        self,
        client: AsyncClient,
        session: SessionModel,
    ):
        with patch("codehive.api.routes.checkpoints._get_git_ops") as mock_get_git:
            mock_ops = AsyncMock()
            mock_ops.commit.return_value = "apisha123"
            mock_get_git.return_value = mock_ops

            resp = await client.post(
                f"/api/sessions/{session.id}/checkpoints",
                json={"label": "test checkpoint"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["session_id"] == str(session.id)
            assert data["git_ref"] == "apisha123"
            assert data["state"]["label"] == "test checkpoint"
            assert data["state"]["status"] == "executing"
            assert "id" in data
            assert "created_at" in data

    async def test_create_nonexistent_session_404(self, client: AsyncClient):
        resp = await client.post(
            f"/api/sessions/{uuid.uuid4()}/checkpoints",
            json={"label": "nope"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestListCheckpointsEndpoint:
    async def test_list_200(
        self,
        client: AsyncClient,
        session: SessionModel,
    ):
        # Create a checkpoint first
        with patch("codehive.api.routes.checkpoints._get_git_ops") as mock_get_git:
            mock_ops = AsyncMock()
            mock_ops.commit.return_value = "listsha"
            mock_get_git.return_value = mock_ops

            await client.post(
                f"/api/sessions/{session.id}/checkpoints",
                json={"label": "cp1"},
            )

        resp = await client.get(f"/api/sessions/{session.id}/checkpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["git_ref"] == "listsha"

    async def test_list_nonexistent_session_404(self, client: AsyncClient):
        resp = await client.get(f"/api/sessions/{uuid.uuid4()}/checkpoints")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestRollbackCheckpointEndpoint:
    async def test_rollback_200(
        self,
        client: AsyncClient,
        session: SessionModel,
    ):
        with patch("codehive.api.routes.checkpoints._get_git_ops") as mock_get_git:
            mock_ops = AsyncMock()
            mock_ops.commit.return_value = "rollsha"
            mock_ops.checkout.return_value = None
            mock_get_git.return_value = mock_ops

            # Create checkpoint
            create_resp = await client.post(
                f"/api/sessions/{session.id}/checkpoints",
                json={"label": "rollback target"},
            )
            checkpoint_id = create_resp.json()["id"]

            # Rollback
            resp = await client.post(f"/api/checkpoints/{checkpoint_id}/rollback")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "executing"
            assert data["mode"] == "execution"
            mock_ops.checkout.assert_awaited_once_with("rollsha")

    async def test_rollback_nonexistent_404(self, client: AsyncClient):
        with patch("codehive.api.routes.checkpoints._get_git_ops") as mock_get_git:
            mock_ops = AsyncMock()
            mock_get_git.return_value = mock_ops

            resp = await client.post(f"/api/checkpoints/{uuid.uuid4()}/rollback")
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Unit tests: NativeEngine auto-checkpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAutoCheckpoint:
    async def _make_engine(self):
        """Build a NativeEngine with all mocked dependencies."""
        from codehive.engine.native import NativeEngine

        client = AsyncMock()
        event_bus = AsyncMock()
        file_ops = AsyncMock()
        shell_runner = AsyncMock()
        git_ops = AsyncMock()
        diff_service = AsyncMock()

        engine = NativeEngine(
            client=client,
            event_bus=event_bus,
            file_ops=file_ops,
            shell_runner=shell_runner,
            git_ops=git_ops,
            diff_service=diff_service,
        )
        return engine, git_ops, file_ops, shell_runner

    async def test_edit_file_triggers_checkpoint(
        self, db_session: AsyncSession, session: SessionModel
    ):
        engine, git_ops, file_ops, _ = await self._make_engine()
        git_ops.commit.return_value = "autochecksha"
        file_ops.edit_file.return_value = "ok"

        with patch("codehive.engine.native.create_checkpoint") as mock_cp:
            mock_cp.return_value = AsyncMock()
            await engine._execute_tool(
                "edit_file",
                {"path": "foo.py", "old_text": "a", "new_text": "b"},
                session_id=session.id,
                db=db_session,
            )
            mock_cp.assert_awaited_once()
            call_kwargs = mock_cp.call_args
            assert call_kwargs.kwargs["label"] == "auto: before edit_file foo.py"

    async def test_run_shell_triggers_checkpoint(
        self, db_session: AsyncSession, session: SessionModel
    ):
        engine, git_ops, _, shell_runner = await self._make_engine()
        git_ops.commit.return_value = "shellsha"

        shell_result = AsyncMock()
        shell_result.stdout = ""
        shell_result.stderr = ""
        shell_result.exit_code = 0
        shell_result.timed_out = False
        shell_runner.run.return_value = shell_result

        with patch("codehive.engine.native.create_checkpoint") as mock_cp:
            mock_cp.return_value = AsyncMock()
            await engine._execute_tool(
                "run_shell",
                {"command": "ls -la"},
                session_id=session.id,
                db=db_session,
            )
            mock_cp.assert_awaited_once()
            call_kwargs = mock_cp.call_args
            assert "auto: before run_shell ls -la" == call_kwargs.kwargs["label"]

    async def test_read_file_does_not_trigger_checkpoint(
        self, db_session: AsyncSession, session: SessionModel
    ):
        engine, git_ops, file_ops, _ = await self._make_engine()
        file_ops.read_file.return_value = "file content"

        with patch("codehive.engine.native.create_checkpoint") as mock_cp:
            await engine._execute_tool(
                "read_file",
                {"path": "foo.py"},
                session_id=session.id,
                db=db_session,
            )
            mock_cp.assert_not_awaited()

    async def test_auto_checkpoint_stores_descriptive_label(
        self, db_session: AsyncSession, session: SessionModel
    ):
        engine, git_ops, file_ops, _ = await self._make_engine()
        git_ops.commit.return_value = "labelsha"
        file_ops.edit_file.return_value = "ok"

        with patch("codehive.engine.native.create_checkpoint") as mock_cp:
            mock_cp.return_value = AsyncMock()
            await engine._execute_tool(
                "edit_file",
                {"path": "src/main.py", "old_text": "old", "new_text": "new"},
                session_id=session.id,
                db=db_session,
            )
            label = mock_cp.call_args.kwargs["label"]
            assert label.startswith("auto: before")
            assert "edit_file" in label
            assert "src/main.py" in label
