"""Tests for tunnel manager, core service layer, and API endpoints.

All SSH and port-forwarding interactions are mocked -- no real SSH server
or port binding is needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from codehive.api.app import create_app
from codehive.core.tunnel import (
    TunnelNotFoundError,
    TunnelTargetNotConnectedError,
    close_tunnel,
    create_tunnel,
    get_preview_url,
    list_active_tunnels,
)
from codehive.execution.ssh import SSHConnectionManager
from codehive.execution.tunnel import (
    Tunnel,
    TunnelCreationError as ExecTunnelCreationError,
    TunnelManager,
    TunnelStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_ssh_manager(connected_targets: set[uuid.UUID] | None = None) -> SSHConnectionManager:
    """Create a mocked SSHConnectionManager with optional connected targets."""
    manager = MagicMock(spec=SSHConnectionManager)
    connected = connected_targets or set()
    manager.has_active_connection = MagicMock(side_effect=lambda tid: tid in connected)

    # Mock the _connections dict
    connections: dict[uuid.UUID, MagicMock] = {}
    for tid in connected:
        conn = MagicMock()
        listener = MagicMock()
        listener.close = MagicMock()
        listener.wait_closed = AsyncMock()
        conn.forward_local_port = AsyncMock(return_value=listener)
        connections[tid] = conn
    manager._connections = connections

    return manager


# ---------------------------------------------------------------------------
# Unit tests: TunnelManager (execution/tunnel.py)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTunnelManagerCreate:
    async def test_create_tunnel_active_status(self):
        target_id = uuid.uuid4()
        ssh = _mock_ssh_manager({target_id})
        tm = TunnelManager(ssh)

        tunnel = await tm.create_tunnel(target_id, 8080, 3000, "dev-server")

        assert tunnel.status == TunnelStatus.ACTIVE
        assert tunnel.target_id == target_id
        assert tunnel.remote_port == 8080
        assert tunnel.local_port == 3000
        assert tunnel.label == "dev-server"

    async def test_create_tunnel_fields(self):
        target_id = uuid.uuid4()
        ssh = _mock_ssh_manager({target_id})
        tm = TunnelManager(ssh)

        tunnel = await tm.create_tunnel(target_id, 8080, 3000, "test")

        assert isinstance(tunnel, Tunnel)
        assert isinstance(tunnel.id, uuid.UUID)
        assert tunnel.target_id == target_id
        assert tunnel.remote_port == 8080
        assert tunnel.local_port == 3000
        assert tunnel.label == "test"
        assert tunnel.status == TunnelStatus.ACTIVE
        assert tunnel.created_at is not None

    async def test_create_tunnel_appears_in_list(self):
        target_id = uuid.uuid4()
        ssh = _mock_ssh_manager({target_id})
        tm = TunnelManager(ssh)

        tunnel = await tm.create_tunnel(target_id, 8080, 3000, "test")

        tunnels = tm.list_tunnels()
        assert len(tunnels) == 1
        assert tunnels[0].id == tunnel.id

    async def test_create_tunnel_no_connection_raises(self):
        ssh = _mock_ssh_manager(set())
        tm = TunnelManager(ssh)

        with pytest.raises(ExecTunnelCreationError, match="no active SSH connection"):
            await tm.create_tunnel(uuid.uuid4(), 8080, 3000, "test")


@pytest.mark.asyncio
class TestTunnelManagerClose:
    async def test_close_tunnel_removes_from_list(self):
        target_id = uuid.uuid4()
        ssh = _mock_ssh_manager({target_id})
        tm = TunnelManager(ssh)

        tunnel = await tm.create_tunnel(target_id, 8080, 3000, "test")
        await tm.close_tunnel(tunnel.id)

        assert tm.list_tunnels() == []

    async def test_close_all_for_target(self):
        target_id = uuid.uuid4()
        ssh = _mock_ssh_manager({target_id})
        tm = TunnelManager(ssh)

        await tm.create_tunnel(target_id, 8080, 3000, "t1")
        await tm.create_tunnel(target_id, 8081, 3001, "t2")

        assert len(tm.list_tunnels()) == 2
        await tm.close_all_for_target(target_id)
        assert len(tm.list_tunnels()) == 0


@pytest.mark.asyncio
class TestTunnelManagerList:
    async def test_list_empty(self):
        ssh = _mock_ssh_manager(set())
        tm = TunnelManager(ssh)
        assert tm.list_tunnels() == []

    async def test_list_filtered_by_target(self):
        t1 = uuid.uuid4()
        t2 = uuid.uuid4()
        ssh = _mock_ssh_manager({t1, t2})
        tm = TunnelManager(ssh)

        await tm.create_tunnel(t1, 8080, 3000, "a")
        await tm.create_tunnel(t2, 8081, 3001, "b")

        assert len(tm.list_tunnels(target_id=t1)) == 1
        assert tm.list_tunnels(target_id=t1)[0].target_id == t1

    async def test_get_tunnel_found(self):
        target_id = uuid.uuid4()
        ssh = _mock_ssh_manager({target_id})
        tm = TunnelManager(ssh)

        tunnel = await tm.create_tunnel(target_id, 8080, 3000, "test")
        found = tm.get_tunnel(tunnel.id)
        assert found is not None
        assert found.id == tunnel.id

    async def test_get_tunnel_not_found(self):
        ssh = _mock_ssh_manager(set())
        tm = TunnelManager(ssh)
        assert tm.get_tunnel(uuid.uuid4()) is None


@pytest.mark.asyncio
class TestTunnelManagerPreview:
    async def test_preview_url(self):
        target_id = uuid.uuid4()
        ssh = _mock_ssh_manager({target_id})
        tm = TunnelManager(ssh)

        tunnel = await tm.create_tunnel(target_id, 8080, 3000, "test")
        url = tm.get_preview_url(tunnel.id)
        assert url == "http://localhost:3000"

    async def test_preview_url_not_found(self):
        ssh = _mock_ssh_manager(set())
        tm = TunnelManager(ssh)
        assert tm.get_preview_url(uuid.uuid4()) is None


@pytest.mark.asyncio
class TestTunnelManagerDisconnect:
    async def test_mark_disconnected(self):
        target_id = uuid.uuid4()
        ssh = _mock_ssh_manager({target_id})
        tm = TunnelManager(ssh)

        tunnel = await tm.create_tunnel(target_id, 8080, 3000, "test")
        affected = tm.mark_disconnected(target_id)

        assert len(affected) == 1
        assert affected[0].id == tunnel.id
        assert affected[0].status == TunnelStatus.DISCONNECTED

    async def test_reestablish_tunnels(self):
        target_id = uuid.uuid4()
        ssh = _mock_ssh_manager({target_id})
        tm = TunnelManager(ssh)

        tunnel = await tm.create_tunnel(target_id, 8080, 3000, "test")
        tm.mark_disconnected(target_id)

        assert tm.get_tunnel(tunnel.id).status == TunnelStatus.DISCONNECTED

        reestablished = await tm.reestablish_tunnels(target_id)
        assert len(reestablished) == 1
        assert reestablished[0].status == TunnelStatus.ACTIVE


# ---------------------------------------------------------------------------
# Unit tests: Core service layer (core/tunnel.py)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCoreTunnelService:
    async def test_create_no_connection_raises(self):
        ssh = _mock_ssh_manager(set())
        tm = TunnelManager(ssh)

        with pytest.raises(TunnelTargetNotConnectedError):
            await create_tunnel(ssh, tm, uuid.uuid4(), 8080, 3000, "test")

    async def test_close_unknown_raises(self):
        ssh = _mock_ssh_manager(set())
        tm = TunnelManager(ssh)

        with pytest.raises(TunnelNotFoundError):
            await close_tunnel(tm, uuid.uuid4())

    async def test_create_delegates_and_returns_tunnel(self):
        target_id = uuid.uuid4()
        ssh = _mock_ssh_manager({target_id})
        tm = TunnelManager(ssh)

        tunnel = await create_tunnel(ssh, tm, target_id, 8080, 3000, "test")
        assert isinstance(tunnel, Tunnel)
        assert tunnel.status == TunnelStatus.ACTIVE

    async def test_list_active_tunnels_delegates(self):
        target_id = uuid.uuid4()
        ssh = _mock_ssh_manager({target_id})
        tm = TunnelManager(ssh)

        await create_tunnel(ssh, tm, target_id, 8080, 3000, "test")
        tunnels = list_active_tunnels(tm)
        assert len(tunnels) == 1

    async def test_get_preview_url_raises_not_found(self):
        ssh = _mock_ssh_manager(set())
        tm = TunnelManager(ssh)

        with pytest.raises(TunnelNotFoundError):
            get_preview_url(tm, uuid.uuid4())


# ---------------------------------------------------------------------------
# Integration tests: API endpoints
# ---------------------------------------------------------------------------


def _make_app_with_mocked_managers(
    connected_targets: set[uuid.UUID] | None = None,
) -> tuple:
    """Create a FastAPI app with mocked SSH and tunnel managers."""
    ssh = _mock_ssh_manager(connected_targets)
    tm = TunnelManager(ssh)
    app = create_app()

    from codehive.api.routes.remote import get_ssh_manager
    from codehive.api.routes.tunnels import get_tunnel_manager

    from codehive.api.deps import get_current_user

    app.dependency_overrides[get_ssh_manager] = lambda: ssh
    app.dependency_overrides[get_tunnel_manager] = lambda: tm
    app.dependency_overrides[get_current_user] = lambda: None

    return app, ssh, tm


@pytest.mark.asyncio
class TestTunnelAPI:
    async def test_create_201(self):
        target_id = uuid.uuid4()
        app, _, _ = _make_app_with_mocked_managers({target_id})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/tunnels",
                json={
                    "target_id": str(target_id),
                    "remote_port": 8080,
                    "local_port": 3000,
                    "label": "dev-server",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["target_id"] == str(target_id)
            assert data["remote_port"] == 8080
            assert data["local_port"] == 3000
            assert data["label"] == "dev-server"
            assert data["status"] == "active"
            assert "id" in data
            assert "created_at" in data

    async def test_create_400_no_connection(self):
        app, _, _ = _make_app_with_mocked_managers(set())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/tunnels",
                json={
                    "target_id": str(uuid.uuid4()),
                    "remote_port": 8080,
                    "local_port": 3000,
                },
            )
            assert resp.status_code == 400

    async def test_list_tunnels(self):
        target_id = uuid.uuid4()
        app, _, _ = _make_app_with_mocked_managers({target_id})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/tunnels",
                json={
                    "target_id": str(target_id),
                    "remote_port": 8080,
                    "local_port": 3000,
                    "label": "t1",
                },
            )
            resp = await client.get("/api/tunnels")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["label"] == "t1"

    async def test_list_tunnels_filter_by_target(self):
        t1 = uuid.uuid4()
        t2 = uuid.uuid4()
        app, _, _ = _make_app_with_mocked_managers({t1, t2})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/tunnels",
                json={"target_id": str(t1), "remote_port": 8080, "local_port": 3000, "label": "a"},
            )
            await client.post(
                "/api/tunnels",
                json={"target_id": str(t2), "remote_port": 8081, "local_port": 3001, "label": "b"},
            )

            resp = await client.get(f"/api/tunnels?target_id={t1}")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["target_id"] == str(t1)

    async def test_get_tunnel_detail(self):
        target_id = uuid.uuid4()
        app, _, _ = _make_app_with_mocked_managers({target_id})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/api/tunnels",
                json={
                    "target_id": str(target_id),
                    "remote_port": 8080,
                    "local_port": 3000,
                    "label": "detail",
                },
            )
            tunnel_id = create_resp.json()["id"]

            resp = await client.get(f"/api/tunnels/{tunnel_id}")
            assert resp.status_code == 200
            assert resp.json()["label"] == "detail"

    async def test_get_tunnel_404(self):
        app, _, _ = _make_app_with_mocked_managers(set())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/tunnels/{uuid.uuid4()}")
            assert resp.status_code == 404

    async def test_delete_tunnel_204(self):
        target_id = uuid.uuid4()
        app, _, _ = _make_app_with_mocked_managers({target_id})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/api/tunnels",
                json={
                    "target_id": str(target_id),
                    "remote_port": 8080,
                    "local_port": 3000,
                },
            )
            tunnel_id = create_resp.json()["id"]

            resp = await client.delete(f"/api/tunnels/{tunnel_id}")
            assert resp.status_code == 204

            # Verify it's gone
            resp = await client.get(f"/api/tunnels/{tunnel_id}")
            assert resp.status_code == 404

    async def test_delete_tunnel_404(self):
        app, _, _ = _make_app_with_mocked_managers(set())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(f"/api/tunnels/{uuid.uuid4()}")
            assert resp.status_code == 404

    async def test_preview_url(self):
        target_id = uuid.uuid4()
        app, _, _ = _make_app_with_mocked_managers({target_id})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/api/tunnels",
                json={
                    "target_id": str(target_id),
                    "remote_port": 8080,
                    "local_port": 3000,
                },
            )
            tunnel_id = create_resp.json()["id"]

            resp = await client.get(f"/api/tunnels/{tunnel_id}/preview")
            assert resp.status_code == 200
            data = resp.json()
            assert data["url"] == "http://localhost:3000"
            assert data["tunnel_id"] == tunnel_id
