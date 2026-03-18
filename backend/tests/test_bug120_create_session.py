"""Bug #120 regression tests: send_message endpoints must call create_session for ClaudeCodeEngine.

TDD: these tests should FAIL before the fix and PASS after.
"""

import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.db.models import Base, Project
from codehive.core.session import create_session

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


@pytest.mark.asyncio
class TestBug120CreateSessionCalled:
    """Verify that send_message endpoints call engine.create_session before send_message."""

    async def test_stream_endpoint_calls_create_session_for_claude_code(
        self, client: AsyncClient, db_session: AsyncSession, project: Project
    ):
        """The stream endpoint should call create_session on ClaudeCodeEngine before send_message."""
        # Create a session with engine=claude_code
        session = await create_session(
            db_session,
            project_id=project.id,
            name="test-cc",
            engine="claude_code",
            mode="execution",
            config={"project_root": "/tmp"},
        )

        # Mock the engine
        mock_engine = MagicMock()
        mock_engine.create_session = AsyncMock()

        async def fake_send_message(sid, content, **kwargs):
            yield {"type": "message.created", "data": {"role": "assistant", "content": "hi"}}

        mock_engine.send_message = fake_send_message

        with patch(
            "codehive.api.routes.sessions._build_engine",
            new_callable=AsyncMock,
            return_value=mock_engine,
        ):
            resp = await client.post(
                f"/api/sessions/{session.id}/messages/stream",
                json={"content": "Hello"},
            )
            assert resp.status_code == 200

            # Parse SSE events
            events = []
            for line in resp.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            # Verify create_session was called
            mock_engine.create_session.assert_called_once_with(session.id)

            # Should have received a message event (not an error)
            assert len(events) > 0
            assert events[0]["type"] != "error", f"Got error: {events[0].get('content')}"

    async def test_batch_endpoint_calls_create_session_for_claude_code(
        self, client: AsyncClient, db_session: AsyncSession, project: Project
    ):
        """The batch endpoint should call create_session on ClaudeCodeEngine before send_message."""
        session = await create_session(
            db_session,
            project_id=project.id,
            name="test-cc-batch",
            engine="claude_code",
            mode="execution",
            config={"project_root": "/tmp"},
        )

        mock_engine = MagicMock()
        mock_engine.create_session = AsyncMock()

        async def fake_send_message(sid, content, **kwargs):
            yield {"type": "message.created", "data": {"role": "assistant", "content": "hi"}}

        mock_engine.send_message = fake_send_message

        with patch(
            "codehive.api.routes.sessions._build_engine",
            new_callable=AsyncMock,
            return_value=mock_engine,
        ):
            resp = await client.post(
                f"/api/sessions/{session.id}/messages",
                json={"content": "Hello"},
            )
            assert resp.status_code == 200

            mock_engine.create_session.assert_called_once_with(session.id)

    async def test_create_session_is_idempotent(
        self, client: AsyncClient, db_session: AsyncSession, project: Project
    ):
        """Calling create_session twice should not break -- it's idempotent."""
        session = await create_session(
            db_session,
            project_id=project.id,
            name="test-idempotent",
            engine="claude_code",
            mode="execution",
            config={"project_root": "/tmp"},
        )

        mock_engine = MagicMock()
        mock_engine.create_session = AsyncMock()  # Should be safe to call multiple times

        async def fake_send_message(sid, content, **kwargs):
            yield {"type": "message.created", "data": {"role": "assistant", "content": "hi"}}

        mock_engine.send_message = fake_send_message

        with patch(
            "codehive.api.routes.sessions._build_engine",
            new_callable=AsyncMock,
            return_value=mock_engine,
        ):
            # Send two messages -- create_session should be called each time (idempotent)
            await client.post(
                f"/api/sessions/{session.id}/messages/stream",
                json={"content": "Hello 1"},
            )
            await client.post(
                f"/api/sessions/{session.id}/messages/stream",
                json={"content": "Hello 2"},
            )

            assert mock_engine.create_session.call_count == 2
