"""Thin service layer for tunnel operations with validation."""

from __future__ import annotations

import uuid

from codehive.execution.ssh import SSHConnectionManager
from codehive.execution.tunnel import Tunnel, TunnelManager


class TunnelNotFoundError(Exception):
    """Raised when a tunnel is not found by ID."""


class TunnelTargetNotConnectedError(Exception):
    """Raised when the target has no active SSH connection."""


class TunnelCreationError(Exception):
    """Raised when tunnel creation fails."""


async def create_tunnel(
    ssh_manager: SSHConnectionManager,
    tunnel_manager: TunnelManager,
    target_id: uuid.UUID,
    remote_port: int,
    local_port: int,
    label: str = "",
) -> Tunnel:
    """Validate the target has an active SSH connection and create a tunnel.

    Args:
        ssh_manager: The SSH connection manager.
        tunnel_manager: The tunnel manager.
        target_id: UUID of the remote target.
        remote_port: Port on the remote host.
        local_port: Local port to bind.
        label: Human-readable label.

    Returns:
        The created Tunnel.

    Raises:
        TunnelTargetNotConnectedError: If the target has no active connection.
        TunnelCreationError: If tunnel creation fails.
    """
    if not ssh_manager.has_active_connection(target_id):
        raise TunnelTargetNotConnectedError(f"Target {target_id} has no active SSH connection")

    try:
        return await tunnel_manager.create_tunnel(
            target_id=target_id,
            remote_port=remote_port,
            local_port=local_port,
            label=label,
        )
    except Exception as exc:
        raise TunnelCreationError(f"Failed to create tunnel: {exc}") from exc


async def close_tunnel(
    tunnel_manager: TunnelManager,
    tunnel_id: uuid.UUID,
) -> None:
    """Close a tunnel by ID.

    Args:
        tunnel_manager: The tunnel manager.
        tunnel_id: UUID of the tunnel to close.

    Raises:
        TunnelNotFoundError: If the tunnel does not exist.
    """
    tunnel = tunnel_manager.get_tunnel(tunnel_id)
    if tunnel is None:
        raise TunnelNotFoundError(f"Tunnel {tunnel_id} not found")
    await tunnel_manager.close_tunnel(tunnel_id)


def list_active_tunnels(
    tunnel_manager: TunnelManager,
    target_id: uuid.UUID | None = None,
) -> list[Tunnel]:
    """List active tunnels, optionally filtered by target.

    Args:
        tunnel_manager: The tunnel manager.
        target_id: Optional target UUID filter.

    Returns:
        List of Tunnel objects.
    """
    return tunnel_manager.list_tunnels(target_id=target_id)


def get_preview_url(
    tunnel_manager: TunnelManager,
    tunnel_id: uuid.UUID,
) -> str:
    """Get the preview URL for a tunnel.

    Args:
        tunnel_manager: The tunnel manager.
        tunnel_id: UUID of the tunnel.

    Returns:
        The preview URL string.

    Raises:
        TunnelNotFoundError: If the tunnel does not exist.
    """
    url = tunnel_manager.get_preview_url(tunnel_id)
    if url is None:
        raise TunnelNotFoundError(f"Tunnel {tunnel_id} not found")
    return url
