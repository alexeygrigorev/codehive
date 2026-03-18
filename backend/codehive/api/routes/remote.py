"""CRUD and SSH operation endpoints for remote targets."""

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from codehive.api.deps import get_db
from codehive.api.schemas.remote import (
    ConnectionStatus,
    RemoteTargetCreate,
    RemoteTargetRead,
    RemoteTargetUpdate,
    SSHCommandRequest,
    SSHCommandResult,
)
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
from codehive.execution.ssh import (
    SSHConnectionError,
    SSHConnectionManager,
    SSHTargetConfig,
)

router = APIRouter(prefix="/api/remote-targets", tags=["remote-targets"])

# Module-level SSH connection manager (singleton per process)
_ssh_manager = SSHConnectionManager()


def get_ssh_manager() -> SSHConnectionManager:
    """Return the SSH connection manager singleton."""
    return _ssh_manager


@router.post("", response_model=RemoteTargetRead, status_code=201)
async def create_remote_target_endpoint(
    body: RemoteTargetCreate,
    db: AsyncSession = Depends(get_db),
) -> RemoteTargetRead:
    try:
        target = await create_remote_target(
            db,
            label=body.label,
            host=body.host,
            port=body.port,
            username=body.username,
            key_path=body.key_path,
            known_hosts_policy=body.known_hosts_policy,
        )
    except RemoteTargetValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return RemoteTargetRead.model_validate(target)


@router.get("", response_model=list[RemoteTargetRead])
async def list_remote_targets_endpoint(
    db: AsyncSession = Depends(get_db),
) -> list[RemoteTargetRead]:
    targets = await list_remote_targets(db)
    return [RemoteTargetRead.model_validate(t) for t in targets]


@router.get("/{target_id}", response_model=RemoteTargetRead)
async def get_remote_target_endpoint(
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RemoteTargetRead:
    target = await get_remote_target(db, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Remote target not found")
    return RemoteTargetRead.model_validate(target)


@router.put("/{target_id}", response_model=RemoteTargetRead)
async def update_remote_target_endpoint(
    target_id: uuid.UUID,
    body: RemoteTargetUpdate,
    db: AsyncSession = Depends(get_db),
) -> RemoteTargetRead:
    fields = body.model_dump(exclude_unset=True)
    try:
        target = await update_remote_target(db, target_id, **fields)
    except RemoteTargetNotFoundError:
        raise HTTPException(status_code=404, detail="Remote target not found")
    return RemoteTargetRead.model_validate(target)


@router.delete("/{target_id}", status_code=204)
async def delete_remote_target_endpoint(
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ssh_manager: SSHConnectionManager = Depends(get_ssh_manager),
) -> None:
    try:
        await delete_remote_target(
            db,
            target_id,
            active_connection_ids=ssh_manager.active_connections,
        )
    except RemoteTargetNotFoundError:
        raise HTTPException(status_code=404, detail="Remote target not found")
    except RemoteTargetHasActiveConnectionError:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete target with an active connection",
        )


@router.post("/{target_id}/test", response_model=ConnectionStatus)
async def test_remote_target_endpoint(
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ssh_manager: SSHConnectionManager = Depends(get_ssh_manager),
) -> ConnectionStatus:
    target = await get_remote_target(db, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Remote target not found")

    config = SSHTargetConfig(
        id=target.id,
        host=target.host,
        port=target.port,
        username=target.username,
        key_path=target.key_path,
        known_hosts_policy=target.known_hosts_policy,
    )

    start = time.monotonic()
    try:
        await ssh_manager.connect(config)
        result = await ssh_manager.execute(target.id, "echo ok", timeout=10.0)
        await ssh_manager.disconnect(target.id)
        elapsed_ms = (time.monotonic() - start) * 1000

        if result.exit_code == 0:
            return ConnectionStatus(
                success=True,
                message="Connection successful",
                duration_ms=round(elapsed_ms, 2),
            )
        else:
            return ConnectionStatus(
                success=False,
                message=f"Command failed with exit code {result.exit_code}",
                duration_ms=round(elapsed_ms, 2),
            )
    except SSHConnectionError as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return ConnectionStatus(
            success=False,
            message=str(exc),
            duration_ms=round(elapsed_ms, 2),
        )


@router.post("/{target_id}/execute", response_model=SSHCommandResult)
async def execute_remote_command_endpoint(
    target_id: uuid.UUID,
    body: SSHCommandRequest,
    db: AsyncSession = Depends(get_db),
    ssh_manager: SSHConnectionManager = Depends(get_ssh_manager),
) -> SSHCommandResult:
    target = await get_remote_target(db, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Remote target not found")

    config = SSHTargetConfig(
        id=target.id,
        host=target.host,
        port=target.port,
        username=target.username,
        key_path=target.key_path,
        known_hosts_policy=target.known_hosts_policy,
    )

    try:
        # Ensure connected
        await ssh_manager.connect(config)
        result = await ssh_manager.execute(target.id, body.command, timeout=body.timeout)
        return SSHCommandResult(
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
        )
    except SSHConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
