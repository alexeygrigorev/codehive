"""Tunnel manager for SSH port forwarding and dev server previews."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from codehive.execution.ssh import SSHConnectionManager


class TunnelStatus(str, Enum):
    """Possible tunnel statuses."""

    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    CLOSED = "closed"


class TunnelCreationError(Exception):
    """Raised when a tunnel cannot be created."""


@dataclass
class Tunnel:
    """Represents a single port-forwarding tunnel."""

    id: uuid.UUID
    target_id: uuid.UUID
    remote_port: int
    local_port: int
    label: str
    status: TunnelStatus
    created_at: datetime
    _listener: object | None = field(default=None, repr=False, compare=False)


class TunnelManager:
    """Manages SSH tunnels (port forwards) via an SSHConnectionManager.

    This class does NOT create SSH connections itself; it relies on
    a provided SSHConnectionManager for the underlying transport.
    """

    def __init__(self, ssh_manager: SSHConnectionManager) -> None:
        self._ssh_manager = ssh_manager
        self._tunnels: dict[uuid.UUID, Tunnel] = {}

    async def create_tunnel(
        self,
        target_id: uuid.UUID,
        remote_port: int,
        local_port: int,
        label: str = "",
    ) -> Tunnel:
        """Establish a local port forward via the SSH connection.

        Args:
            target_id: UUID of the remote target.
            remote_port: Port on the remote host to forward.
            local_port: Local port to bind.
            label: Human-readable label for the tunnel.

        Returns:
            A Tunnel dataclass with status ``active``.

        Raises:
            TunnelCreationError: If the target has no active SSH connection
                or port forwarding fails.
        """
        if not self._ssh_manager.has_active_connection(target_id):
            raise TunnelCreationError(f"Target {target_id} has no active SSH connection")

        conn = self._ssh_manager._connections.get(target_id)
        listener: object | None = None
        if conn is not None:
            try:
                listener = await conn.forward_local_port("", local_port, "localhost", remote_port)
            except Exception as exc:
                raise TunnelCreationError(f"Failed to create tunnel: {exc}") from exc

        tunnel = Tunnel(
            id=uuid.uuid4(),
            target_id=target_id,
            remote_port=remote_port,
            local_port=local_port,
            label=label,
            status=TunnelStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            _listener=listener,
        )
        self._tunnels[tunnel.id] = tunnel
        return tunnel

    async def close_tunnel(self, tunnel_id: uuid.UUID) -> None:
        """Stop a port forward and remove from the registry.

        Args:
            tunnel_id: UUID of the tunnel to close.
        """
        tunnel = self._tunnels.pop(tunnel_id, None)
        if tunnel is None:
            return
        tunnel.status = TunnelStatus.CLOSED
        if tunnel._listener is not None:
            try:
                tunnel._listener.close()
                await tunnel._listener.wait_closed()
            except Exception:
                pass

    async def close_all_for_target(self, target_id: uuid.UUID) -> None:
        """Close all tunnels associated with a specific remote target.

        Args:
            target_id: UUID of the target.
        """
        ids_to_close = [tid for tid, t in self._tunnels.items() if t.target_id == target_id]
        for tid in ids_to_close:
            await self.close_tunnel(tid)

    def list_tunnels(self, target_id: uuid.UUID | None = None) -> list[Tunnel]:
        """Return all active tunnels, optionally filtered by target_id.

        Args:
            target_id: Optional filter.

        Returns:
            List of Tunnel objects.
        """
        tunnels = list(self._tunnels.values())
        if target_id is not None:
            tunnels = [t for t in tunnels if t.target_id == target_id]
        return tunnels

    def get_tunnel(self, tunnel_id: uuid.UUID) -> Tunnel | None:
        """Return a single tunnel by ID, or None if not found.

        Args:
            tunnel_id: UUID of the tunnel.

        Returns:
            The Tunnel or None.
        """
        return self._tunnels.get(tunnel_id)

    def get_preview_url(self, tunnel_id: uuid.UUID) -> str | None:
        """Generate a preview URL for a tunnel.

        Args:
            tunnel_id: UUID of the tunnel.

        Returns:
            URL string like ``http://localhost:{local_port}`` or None.
        """
        tunnel = self._tunnels.get(tunnel_id)
        if tunnel is None:
            return None
        return f"http://localhost:{tunnel.local_port}"

    def mark_disconnected(self, target_id: uuid.UUID) -> list[Tunnel]:
        """Mark all tunnels for a target as disconnected.

        Called when the SSH connection for a target drops.

        Args:
            target_id: UUID of the target.

        Returns:
            List of tunnels that were marked disconnected.
        """
        affected: list[Tunnel] = []
        for tunnel in self._tunnels.values():
            if tunnel.target_id == target_id and tunnel.status == TunnelStatus.ACTIVE:
                tunnel.status = TunnelStatus.DISCONNECTED
                tunnel._listener = None
                affected.append(tunnel)
        return affected

    async def reestablish_tunnels(self, target_id: uuid.UUID) -> list[Tunnel]:
        """Re-establish disconnected tunnels for a target that has reconnected.

        Args:
            target_id: UUID of the target.

        Returns:
            List of tunnels that were successfully re-established.
        """
        reestablished: list[Tunnel] = []
        disconnected = [
            t
            for t in self._tunnels.values()
            if t.target_id == target_id and t.status == TunnelStatus.DISCONNECTED
        ]

        for tunnel in disconnected:
            if not self._ssh_manager.has_active_connection(target_id):
                break

            conn = self._ssh_manager._connections.get(target_id)
            listener: object | None = None
            if conn is not None:
                try:
                    listener = await conn.forward_local_port(
                        "", tunnel.local_port, "localhost", tunnel.remote_port
                    )
                except Exception:
                    continue

            tunnel.status = TunnelStatus.ACTIVE
            tunnel._listener = listener
            reestablished.append(tunnel)

        return reestablished
