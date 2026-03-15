"""API endpoints for tunnel management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from codehive.api.routes.remote import get_ssh_manager
from codehive.api.schemas.tunnel import TunnelCreate, TunnelPreviewURL, TunnelRead
from codehive.core.tunnel import (
    TunnelCreationError,
    TunnelNotFoundError,
    TunnelTargetNotConnectedError,
    close_tunnel,
    create_tunnel,
    get_preview_url,
    list_active_tunnels,
)
from codehive.execution.ssh import SSHConnectionManager
from codehive.execution.tunnel import TunnelManager

router = APIRouter(prefix="/api/tunnels", tags=["tunnels"])

# Module-level tunnel manager (created lazily, depends on SSH manager)
_tunnel_manager: TunnelManager | None = None


def get_tunnel_manager(
    ssh_manager: SSHConnectionManager = Depends(get_ssh_manager),
) -> TunnelManager:
    """Return the tunnel manager singleton, creating it if needed."""
    global _tunnel_manager
    if _tunnel_manager is None or _tunnel_manager._ssh_manager is not ssh_manager:
        _tunnel_manager = TunnelManager(ssh_manager)
    return _tunnel_manager


def _tunnel_to_read(tunnel: object) -> TunnelRead:
    """Convert a Tunnel dataclass to a TunnelRead schema."""
    return TunnelRead(
        id=tunnel.id,  # type: ignore[attr-defined]
        target_id=tunnel.target_id,  # type: ignore[attr-defined]
        remote_port=tunnel.remote_port,  # type: ignore[attr-defined]
        local_port=tunnel.local_port,  # type: ignore[attr-defined]
        label=tunnel.label,  # type: ignore[attr-defined]
        status=tunnel.status.value if hasattr(tunnel.status, "value") else tunnel.status,  # type: ignore[attr-defined]
        created_at=tunnel.created_at,  # type: ignore[attr-defined]
    )


@router.post("", response_model=TunnelRead, status_code=201)
async def create_tunnel_endpoint(
    body: TunnelCreate,
    ssh_manager: SSHConnectionManager = Depends(get_ssh_manager),
    tunnel_manager: TunnelManager = Depends(get_tunnel_manager),
) -> TunnelRead:
    """Create a new tunnel (port forward)."""
    try:
        tunnel = await create_tunnel(
            ssh_manager=ssh_manager,
            tunnel_manager=tunnel_manager,
            target_id=body.target_id,
            remote_port=body.remote_port,
            local_port=body.local_port,
            label=body.label,
        )
    except TunnelTargetNotConnectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except TunnelCreationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _tunnel_to_read(tunnel)


@router.get("", response_model=list[TunnelRead])
async def list_tunnels_endpoint(
    target_id: uuid.UUID | None = None,
    tunnel_manager: TunnelManager = Depends(get_tunnel_manager),
) -> list[TunnelRead]:
    """List active tunnels, optionally filtered by target_id."""
    tunnels = list_active_tunnels(tunnel_manager, target_id=target_id)
    return [_tunnel_to_read(t) for t in tunnels]


@router.get("/{tunnel_id}", response_model=TunnelRead)
async def get_tunnel_endpoint(
    tunnel_id: uuid.UUID,
    tunnel_manager: TunnelManager = Depends(get_tunnel_manager),
) -> TunnelRead:
    """Get a single tunnel by ID."""
    tunnel = tunnel_manager.get_tunnel(tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="Tunnel not found")
    return _tunnel_to_read(tunnel)


@router.delete("/{tunnel_id}", status_code=204)
async def delete_tunnel_endpoint(
    tunnel_id: uuid.UUID,
    tunnel_manager: TunnelManager = Depends(get_tunnel_manager),
) -> None:
    """Close a tunnel."""
    try:
        await close_tunnel(tunnel_manager, tunnel_id)
    except TunnelNotFoundError:
        raise HTTPException(status_code=404, detail="Tunnel not found")


@router.get("/{tunnel_id}/preview", response_model=TunnelPreviewURL)
async def get_tunnel_preview_endpoint(
    tunnel_id: uuid.UUID,
    tunnel_manager: TunnelManager = Depends(get_tunnel_manager),
) -> TunnelPreviewURL:
    """Get the preview URL for a tunnel."""
    try:
        url = get_preview_url(tunnel_manager, tunnel_id)
    except TunnelNotFoundError:
        raise HTTPException(status_code=404, detail="Tunnel not found")
    return TunnelPreviewURL(tunnel_id=tunnel_id, url=url)
