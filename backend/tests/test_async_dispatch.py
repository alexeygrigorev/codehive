"""Tests for async message dispatch endpoint (POST /api/sessions/{id}/messages/async).

Covers: Part A of issue #99 -- non-blocking engine dispatch.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.api.routes.async_dispatch import (
    _run_engine_background,
    _running_tasks,
    get_db_factory,
)
from codehive.core.session import get_session, update_session
from codehive.db.models import Base, Project
from codehive.db.models import Session as SessionModel

# Use file-based SQLite with shared cache so multiple connections see the same data
SQLITE_URL = "sqlite+aiosqlite:///file:test_async_dispatch?mode=memory&cache=shared&uri=true"


@pytest_asyncio.fixture
async def db_engine():
    """Create a shared async engine for tests."""
    engine = create_async_engine(SQLITE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_factory(db_engine):
    """Return an async_sessionmaker bound to the test engine."""
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(db_factory) -> AsyncGenerator[AsyncSession, None]:
    async with db_factory() as session:
        yield session


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
async def session_row(db_session: AsyncSession, project: Project) -> SessionModel:
    """Create a session in idle state."""
    s = SessionModel(
        project_id=project.id,
        name="test-session",
        engine="native",
        mode="execution",
        status="idle",
        config={"project_root": "/tmp"},
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def client(db_factory, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with db_factory() as session:
            yield session

    def _override_get_db_factory():
        return db_factory

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_db_factory] = _override_get_db_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/register",
            json={"email": "test@test.com", "username": "testuser", "password": "testpass"},
        )
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac

    # Clean up any running tasks after each test -- wait briefly first
    for task in list(_running_tasks.values()):
        if not task.done():
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (asyncio.TimeoutError, Exception):
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
    _running_tasks.clear()


# ---------------------------------------------------------------------------
# Mock engine that yields events and completes
# ---------------------------------------------------------------------------


class _MockEngine:
    """Fake engine whose ``send_message`` yields events then returns."""

    def __init__(self, events: list[dict[str, Any]] | None = None, delay: float = 0.0):
        self._events = events or [
            {"type": "message.created", "role": "assistant", "content": "hello"},
        ]
        self._delay = delay

    async def send_message(
        self,
        session_id: uuid.UUID,
        content: str,
        db: AsyncSession | None = None,
    ):
        if self._delay:
            await asyncio.sleep(self._delay)
        for ev in self._events:
            yield ev


# ---------------------------------------------------------------------------
# Tests: HTTP endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAsyncDispatchEndpoint:
    async def test_returns_202_with_running_status(
        self, client: AsyncClient, session_row: SessionModel
    ) -> None:
        """POST /api/sessions/{id}/messages/async returns 202 and status running."""
        with patch(
            "codehive.api.routes.sessions._build_engine",
            return_value=_MockEngine(),
        ):
            resp = await client.post(
                f"/api/sessions/{session_row.id}/messages/async",
                json={"content": "hello"},
            )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "running"

    async def test_session_not_found_404(self, client: AsyncClient) -> None:
        """POST with invalid session ID returns 404."""
        resp = await client.post(
            f"/api/sessions/{uuid.uuid4()}/messages/async",
            json={"content": "hello"},
        )
        assert resp.status_code == 404

    async def test_conflict_when_already_running(
        self, client: AsyncClient, session_row: SessionModel
    ) -> None:
        """Second POST while engine is running returns 409."""
        with patch(
            "codehive.api.routes.sessions._build_engine",
            return_value=_MockEngine(delay=5.0),
        ):
            resp1 = await client.post(
                f"/api/sessions/{session_row.id}/messages/async",
                json={"content": "first"},
            )
            assert resp1.status_code == 202

            # Second request should conflict
            resp2 = await client.post(
                f"/api/sessions/{session_row.id}/messages/async",
                json={"content": "second"},
            )
            assert resp2.status_code == 409

    async def test_session_status_changes_to_executing(
        self, client: AsyncClient, session_row: SessionModel
    ) -> None:
        """After async dispatch, session status becomes executing."""
        with patch(
            "codehive.api.routes.sessions._build_engine",
            return_value=_MockEngine(delay=0.5),
        ):
            resp = await client.post(
                f"/api/sessions/{session_row.id}/messages/async",
                json={"content": "work"},
            )
            assert resp.status_code == 202

            # Check status via API (while task is still running)
            resp = await client.get(f"/api/sessions/{session_row.id}")
            assert resp.status_code == 200
            assert resp.json()["status"] == "executing"


# ---------------------------------------------------------------------------
# Tests: Background task behavior (unit tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBackgroundTaskBehavior:
    async def test_status_returns_to_waiting_input_after_completion(
        self, db_factory, session_row: SessionModel
    ) -> None:
        """After the engine finishes, session status becomes waiting_input."""
        mock_engine = _MockEngine(delay=0.05)

        # Set session to executing first
        async with db_factory() as db:
            await update_session(db, session_row.id, status="executing")

        await _run_engine_background(session_row.id, "quick task", mock_engine, db_factory)

        async with db_factory() as db:
            session = await get_session(db, session_row.id)
            assert session is not None
            assert session.status == "waiting_input"

    async def test_status_becomes_failed_on_engine_error(
        self, db_factory, session_row: SessionModel
    ) -> None:
        """If the engine raises, session status becomes failed."""

        class _FailingEngine:
            async def send_message(self, session_id, content, db=None):
                raise RuntimeError("Engine exploded")
                yield  # make it an async generator  # noqa: E501

        # Set session to executing first
        async with db_factory() as db:
            await update_session(db, session_row.id, status="executing")

        await _run_engine_background(session_row.id, "kaboom", _FailingEngine(), db_factory)

        async with db_factory() as db:
            session = await get_session(db, session_row.id)
            assert session is not None
            assert session.status == "failed"

    async def test_disconnect_does_not_stop_engine(
        self, client: AsyncClient, session_row: SessionModel
    ) -> None:
        """Starting async dispatch and returning does not stop the engine."""
        mock_engine = _MockEngine(delay=0.5)

        with patch(
            "codehive.api.routes.sessions._build_engine",
            return_value=mock_engine,
        ):
            resp = await client.post(
                f"/api/sessions/{session_row.id}/messages/async",
                json={"content": "long task"},
            )
            assert resp.status_code == 202

        # The task should still be running even though the HTTP request is done
        task = _running_tasks.get(session_row.id)
        assert task is not None
        assert not task.done()

        # Wait for it to complete
        await asyncio.wait_for(task, timeout=5.0)
        assert task.done()

    async def test_task_removed_from_registry_after_completion(
        self, db_factory, session_row: SessionModel
    ) -> None:
        """After the engine finishes, the task is removed from _running_tasks."""
        mock_engine = _MockEngine(delay=0.05)

        # Set session to executing first
        async with db_factory() as db:
            await update_session(db, session_row.id, status="executing")

        # Simulate what the endpoint does
        task = asyncio.create_task(
            _run_engine_background(session_row.id, "quick", mock_engine, db_factory),
        )
        _running_tasks[session_row.id] = task

        await asyncio.wait_for(task, timeout=5.0)

        # Small delay for finally block
        await asyncio.sleep(0.1)

        assert session_row.id not in _running_tasks

    async def test_engine_completes_and_updates_status(
        self, db_factory, session_row: SessionModel
    ) -> None:
        """Full lifecycle: task runs, completes, updates status, removes from registry."""
        events = [
            {"type": "message.created", "role": "assistant", "content": "Done!"},
        ]
        mock_engine = _MockEngine(events=events, delay=0.05)

        async with db_factory() as db:
            await update_session(db, session_row.id, status="executing")

        task = asyncio.create_task(
            _run_engine_background(session_row.id, "test", mock_engine, db_factory),
        )
        _running_tasks[session_row.id] = task

        await asyncio.wait_for(task, timeout=5.0)
        await asyncio.sleep(0.1)

        # Verify final state
        async with db_factory() as db:
            session = await get_session(db, session_row.id)
            assert session is not None
            assert session.status == "waiting_input"
        assert session_row.id not in _running_tasks
