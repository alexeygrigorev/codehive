"""Tests for SSH connection manager, remote target CRUD, and API endpoints.

All SSH interactions are mocked -- no real SSH server is needed.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codehive.api.app import create_app
from codehive.api.deps import get_db
from codehive.core.remote import (
    RemoteTargetHasActiveConnectionError,
    RemoteTargetNotFoundError,
    RemoteTargetValidationError,
    create_remote_target,
    delete_remote_target,
    get_remote_target,
    list_remote_targets,
    update_remote_target,
)
from codehive.db.models import Base
from codehive.execution.shell import ShellResult
from codehive.execution.ssh import (
    SSHConnectionError,
    SSHConnectionManager,
    SSHTargetConfig,
    SSHTargetNotConnectedError,
)

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
# Unit tests: Remote target CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreCreateRemoteTarget:
    async def test_create_success(self, db_session: AsyncSession):
        target = await create_remote_target(
            db_session,
            label="prod-server",
            host="192.168.1.100",
            username="deploy",
            port=22,
        )
        assert target.id is not None
        assert isinstance(target.id, uuid.UUID)
        assert target.host == "192.168.1.100"
        assert target.username == "deploy"
        assert target.port == 22
        assert target.status == "disconnected"
        assert target.known_hosts_policy == "auto"

    async def test_create_missing_host(self, db_session: AsyncSession):
        with pytest.raises(RemoteTargetValidationError, match="host is required"):
            await create_remote_target(
                db_session,
                label="bad",
                host="",
                username="user",
            )

    async def test_create_missing_username(self, db_session: AsyncSession):
        with pytest.raises(RemoteTargetValidationError, match="username is required"):
            await create_remote_target(
                db_session,
                label="bad",
                host="host.example.com",
                username="",
            )


@pytest.mark.asyncio
class TestCoreListRemoteTargets:
    async def test_list_filtered_by_workspace(self, db_session: AsyncSession):
        await create_remote_target(
            db_session,
            label="server-1",
            host="10.0.0.1",
            username="admin",
        )
        await create_remote_target(
            db_session,
            label="server-2",
            host="10.0.0.2",
            username="admin",
        )
        targets = await list_remote_targets(db_session)
        assert len(targets) == 2


@pytest.mark.asyncio
class TestCoreGetRemoteTarget:
    async def test_get_existing(self, db_session: AsyncSession):
        created = await create_remote_target(
            db_session,
            label="get-me",
            host="10.0.0.1",
            username="admin",
        )
        found = await get_remote_target(db_session, created.id)
        assert found is not None
        assert found.id == created.id
        assert found.host == "10.0.0.1"

    async def test_get_nonexistent(self, db_session: AsyncSession):
        result = await get_remote_target(db_session, uuid.uuid4())
        assert result is None


@pytest.mark.asyncio
class TestCoreUpdateRemoteTarget:
    async def test_update_host_and_port(self, db_session: AsyncSession):
        created = await create_remote_target(
            db_session,
            label="update-me",
            host="10.0.0.1",
            username="admin",
        )
        updated = await update_remote_target(db_session, created.id, host="10.0.0.2", port=2222)
        assert updated.host == "10.0.0.2"
        assert updated.port == 2222

    async def test_update_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(RemoteTargetNotFoundError):
            await update_remote_target(db_session, uuid.uuid4(), host="x")


@pytest.mark.asyncio
class TestCoreDeleteRemoteTarget:
    async def test_delete_success(self, db_session: AsyncSession):
        created = await create_remote_target(
            db_session,
            label="del-me",
            host="10.0.0.1",
            username="admin",
        )
        await delete_remote_target(db_session, created.id)
        assert await get_remote_target(db_session, created.id) is None

    async def test_delete_nonexistent(self, db_session: AsyncSession):
        with pytest.raises(RemoteTargetNotFoundError):
            await delete_remote_target(db_session, uuid.uuid4())

    async def test_delete_with_active_connection(self, db_session: AsyncSession):
        created = await create_remote_target(
            db_session,
            label="active",
            host="10.0.0.1",
            username="admin",
        )
        with pytest.raises(RemoteTargetHasActiveConnectionError):
            await delete_remote_target(db_session, created.id, active_connection_ids={created.id})


# ---------------------------------------------------------------------------
# Unit tests: SSHConnectionManager (all SSH mocked)
# ---------------------------------------------------------------------------


def _make_config(target_id: uuid.UUID | None = None) -> SSHTargetConfig:
    """Create a test SSH target config."""
    return SSHTargetConfig(
        id=target_id or uuid.uuid4(),
        host="10.0.0.1",
        port=22,
        username="testuser",
        known_hosts_policy="ignore",
    )


def _mock_ssh_connection() -> MagicMock:
    """Create a mocked asyncssh SSHClientConnection."""
    conn = MagicMock()
    conn.close = MagicMock()
    conn.wait_closed = AsyncMock()

    # Mock run() to return a successful result
    run_result = MagicMock()
    run_result.exit_status = 0
    run_result.stdout = "output\n"
    run_result.stderr = ""
    conn.run = AsyncMock(return_value=run_result)

    # Mock SFTP
    sftp = AsyncMock()
    sftp.put = AsyncMock()
    sftp.get = AsyncMock()
    sftp_ctx = AsyncMock()
    sftp_ctx.__aenter__ = AsyncMock(return_value=sftp)
    sftp_ctx.__aexit__ = AsyncMock(return_value=False)
    conn.start_sftp_client = MagicMock(return_value=sftp_ctx)

    return conn


@pytest.mark.asyncio
class TestSSHConnectionManager:
    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_connect_stores_in_pool(self, mock_connect: AsyncMock):
        mock_conn = _mock_ssh_connection()
        mock_connect.return_value = mock_conn

        manager = SSHConnectionManager()
        config = _make_config()
        await manager.connect(config)

        assert manager.has_active_connection(config.id)
        mock_connect.assert_called_once()

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_execute_returns_shell_result(self, mock_connect: AsyncMock):
        mock_conn = _mock_ssh_connection()
        mock_connect.return_value = mock_conn

        manager = SSHConnectionManager()
        config = _make_config()
        await manager.connect(config)

        result = await manager.execute(config.id, "ls -la")
        assert isinstance(result, ShellResult)
        assert result.exit_code == 0
        assert result.stdout == "output\n"
        assert result.stderr == ""
        assert result.timed_out is False

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_execute_with_timeout(self, mock_connect: AsyncMock):
        mock_conn = _mock_ssh_connection()
        # Make run() hang to trigger timeout
        import asyncio

        async def slow_run(*args, **kwargs):
            await asyncio.sleep(10)

        mock_conn.run = slow_run
        mock_connect.return_value = mock_conn

        manager = SSHConnectionManager()
        config = _make_config()
        await manager.connect(config)

        result = await manager.execute(config.id, "slow-cmd", timeout=0.1)
        assert result.timed_out is True
        assert result.exit_code == -1

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_upload_file(self, mock_connect: AsyncMock):
        mock_conn = _mock_ssh_connection()
        mock_connect.return_value = mock_conn

        manager = SSHConnectionManager()
        config = _make_config()
        await manager.connect(config)

        await manager.upload(config.id, "/tmp/local.txt", "/tmp/remote.txt")

        sftp = await mock_conn.start_sftp_client().__aenter__()
        sftp.put.assert_called_once_with("/tmp/local.txt", "/tmp/remote.txt")

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_download_file(self, mock_connect: AsyncMock):
        mock_conn = _mock_ssh_connection()
        mock_connect.return_value = mock_conn

        manager = SSHConnectionManager()
        config = _make_config()
        await manager.connect(config)

        await manager.download(config.id, "/tmp/remote.txt", "/tmp/local.txt")

        sftp = await mock_conn.start_sftp_client().__aenter__()
        sftp.get.assert_called_once_with("/tmp/remote.txt", "/tmp/local.txt")

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_check_liveness_alive(self, mock_connect: AsyncMock):
        mock_conn = _mock_ssh_connection()
        mock_connect.return_value = mock_conn

        manager = SSHConnectionManager()
        config = _make_config()
        await manager.connect(config)

        alive = await manager.check_liveness(config.id)
        assert alive is True

    async def test_check_liveness_not_connected(self):
        manager = SSHConnectionManager()
        alive = await manager.check_liveness(uuid.uuid4())
        assert alive is False

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_check_liveness_dead_connection(self, mock_connect: AsyncMock):
        mock_conn = _mock_ssh_connection()
        mock_conn.run = AsyncMock(side_effect=OSError("Connection lost"))
        mock_connect.return_value = mock_conn

        manager = SSHConnectionManager()
        config = _make_config()
        await manager.connect(config)

        alive = await manager.check_liveness(config.id)
        assert alive is False

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_auto_reconnect_on_connection_loss(self, mock_connect: AsyncMock):
        """Simulate connection drop during execute, verify reconnect and retry."""
        import asyncssh

        mock_conn_1 = _mock_ssh_connection()
        # First call to run raises ConnectionLost
        mock_conn_1.run = AsyncMock(side_effect=asyncssh.ConnectionLost("Connection lost"))

        mock_conn_2 = _mock_ssh_connection()
        # Second connection works fine
        run_result = MagicMock()
        run_result.exit_status = 0
        run_result.stdout = "reconnected\n"
        run_result.stderr = ""
        mock_conn_2.run = AsyncMock(return_value=run_result)

        mock_connect.side_effect = [mock_conn_1, mock_conn_2]

        manager = SSHConnectionManager()
        config = _make_config()
        await manager.connect(config)

        result = await manager.execute(config.id, "echo hello")
        assert result.exit_code == 0
        assert result.stdout == "reconnected\n"
        assert mock_connect.call_count == 2

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_disconnect_removes_from_pool(self, mock_connect: AsyncMock):
        mock_conn = _mock_ssh_connection()
        mock_connect.return_value = mock_conn

        manager = SSHConnectionManager()
        config = _make_config()
        await manager.connect(config)
        assert manager.has_active_connection(config.id)

        await manager.disconnect(config.id)
        assert not manager.has_active_connection(config.id)

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_execute_auto_connects(self, mock_connect: AsyncMock):
        """Calling execute on a disconnected target auto-connects."""
        mock_conn = _mock_ssh_connection()
        mock_connect.return_value = mock_conn

        manager = SSHConnectionManager()
        config = _make_config()
        # Register config via connect, then disconnect
        await manager.connect(config)
        await manager.disconnect(config.id)

        # Re-register config so auto-connect knows about it
        manager._configs[config.id] = config

        result = await manager.execute(config.id, "echo hello")
        assert result.exit_code == 0

    async def test_execute_unknown_target_raises(self):
        manager = SSHConnectionManager()
        with pytest.raises(SSHTargetNotConnectedError):
            await manager.execute(uuid.uuid4(), "echo hello")

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_connect_failure_raises(self, mock_connect: AsyncMock):
        mock_connect.side_effect = OSError("Connection refused")

        manager = SSHConnectionManager()
        config = _make_config()
        with pytest.raises(SSHConnectionError, match="Connection refused"):
            await manager.connect(config)


# ---------------------------------------------------------------------------
# Integration tests: API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRemoteTargetAPI:
    async def test_create_201(self, client: AsyncClient):
        resp = await client.post(
            "/api/remote-targets",
            json={
                "label": "my-server",
                "host": "10.0.0.1",
                "port": 22,
                "username": "deploy",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["host"] == "10.0.0.1"
        assert data["username"] == "deploy"
        assert data["port"] == 22
        assert data["status"] == "disconnected"
        assert "id" in data

    async def test_list_includes_created(self, client: AsyncClient):
        await client.post(
            "/api/remote-targets",
            json={
                "label": "srv-1",
                "host": "10.0.0.1",
                "username": "user",
            },
        )
        resp = await client.get("/api/remote-targets")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_detail(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/remote-targets",
            json={
                "label": "detail-srv",
                "host": "10.0.0.2",
                "username": "admin",
            },
        )
        target_id = create_resp.json()["id"]
        resp = await client.get(f"/api/remote-targets/{target_id}")
        assert resp.status_code == 200
        assert resp.json()["host"] == "10.0.0.2"

    async def test_update_fields(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/remote-targets",
            json={
                "label": "upd-srv",
                "host": "10.0.0.1",
                "username": "admin",
            },
        )
        target_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/remote-targets/{target_id}",
            json={"host": "10.0.0.99", "port": 2222},
        )
        assert resp.status_code == 200
        assert resp.json()["host"] == "10.0.0.99"
        assert resp.json()["port"] == 2222

    async def test_delete_removes(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/remote-targets",
            json={
                "label": "del-srv",
                "host": "10.0.0.1",
                "username": "admin",
            },
        )
        target_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/remote-targets/{target_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/remote-targets/{target_id}")
        assert resp.status_code == 404

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_test_connection_success(self, mock_connect: AsyncMock, client: AsyncClient):
        mock_conn = _mock_ssh_connection()
        mock_connect.return_value = mock_conn

        create_resp = await client.post(
            "/api/remote-targets",
            json={
                "label": "test-srv",
                "host": "10.0.0.1",
                "username": "admin",
                "known_hosts_policy": "ignore",
            },
        )
        target_id = create_resp.json()["id"]
        resp = await client.post(f"/api/remote-targets/{target_id}/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["duration_ms"] is not None

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_test_connection_failure(self, mock_connect: AsyncMock, client: AsyncClient):
        mock_connect.side_effect = OSError("Connection refused")

        create_resp = await client.post(
            "/api/remote-targets",
            json={
                "label": "fail-srv",
                "host": "unreachable.example.com",
                "username": "admin",
                "known_hosts_policy": "ignore",
            },
        )
        target_id = create_resp.json()["id"]
        resp = await client.post(f"/api/remote-targets/{target_id}/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "Connection refused" in data["message"]

    @patch("codehive.execution.ssh.asyncssh.connect", new_callable=AsyncMock)
    async def test_execute_command(self, mock_connect: AsyncMock, client: AsyncClient):
        mock_conn = _mock_ssh_connection()
        mock_connect.return_value = mock_conn

        create_resp = await client.post(
            "/api/remote-targets",
            json={
                "label": "exec-srv",
                "host": "10.0.0.1",
                "username": "admin",
                "known_hosts_policy": "ignore",
            },
        )
        target_id = create_resp.json()["id"]
        resp = await client.post(
            f"/api/remote-targets/{target_id}/execute",
            json={"command": "ls -la", "timeout": 10},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["exit_code"] == 0
        assert data["stdout"] == "output\n"
        assert data["timed_out"] is False

    async def test_delete_with_active_connection_400(self, client: AsyncClient):
        """Simulate that the target has an active connection by injecting it into the manager."""
        create_resp = await client.post(
            "/api/remote-targets",
            json={
                "label": "active-srv",
                "host": "10.0.0.1",
                "username": "admin",
            },
        )
        target_id = create_resp.json()["id"]

        # Inject the target_id into the SSH manager's connection pool
        from codehive.api.routes.remote import _ssh_manager

        _ssh_manager._connections[uuid.UUID(target_id)] = _mock_ssh_connection()

        try:
            resp = await client.delete(f"/api/remote-targets/{target_id}")
            assert resp.status_code == 400
            assert "active connection" in resp.json()["detail"]
        finally:
            # Clean up
            _ssh_manager._connections.pop(uuid.UUID(target_id), None)
