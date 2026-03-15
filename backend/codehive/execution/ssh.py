"""SSH connection manager with connection pooling and auto-reconnect."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from pathlib import Path

import asyncssh

from codehive.execution.shell import ShellResult


class SSHConnectionError(Exception):
    """Raised when an SSH connection cannot be established."""


class SSHTargetNotConnectedError(Exception):
    """Raised when an operation is attempted on a target with no active connection."""


@dataclass
class SSHTargetConfig:
    """Configuration needed to establish an SSH connection."""

    id: uuid.UUID
    host: str
    port: int
    username: str
    key_path: str | None = None
    known_hosts_policy: str = "auto"


class SSHConnectionManager:
    """Manages SSH connections with pooling and auto-reconnect.

    Tracks active connections by target_id and reuses them.
    """

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, asyncssh.SSHClientConnection] = {}
        self._configs: dict[uuid.UUID, SSHTargetConfig] = {}

    @property
    def active_connections(self) -> set[uuid.UUID]:
        """Return set of target IDs with active connections."""
        return set(self._connections.keys())

    def has_active_connection(self, target_id: uuid.UUID) -> bool:
        """Check if the target has an active connection in the pool."""
        return target_id in self._connections

    async def connect(self, config: SSHTargetConfig) -> None:
        """Establish an SSH connection using the given target config.

        If a connection already exists for this target, it is reused.

        Args:
            config: SSH target configuration.

        Raises:
            SSHConnectionError: If the connection fails.
        """
        if config.id in self._connections:
            return

        self._configs[config.id] = config
        await self._establish_connection(config)

    async def _establish_connection(self, config: SSHTargetConfig) -> None:
        """Internal method to create the actual SSH connection."""
        connect_kwargs: dict = {
            "host": config.host,
            "port": config.port,
            "username": config.username,
        }

        if config.key_path:
            connect_kwargs["client_keys"] = [config.key_path]

        if config.known_hosts_policy == "ignore":
            connect_kwargs["known_hosts"] = None
        # For "auto" and other policies, let asyncssh handle it with defaults

        try:
            conn = await asyncssh.connect(**connect_kwargs)
            self._connections[config.id] = conn
        except Exception as exc:
            raise SSHConnectionError(
                f"Failed to connect to {config.host}:{config.port}: {exc}"
            ) from exc

    async def disconnect(self, target_id: uuid.UUID) -> None:
        """Close an active connection and remove it from the pool.

        Args:
            target_id: UUID of the target to disconnect.
        """
        conn = self._connections.pop(target_id, None)
        if conn is not None:
            conn.close()
            await conn.wait_closed()
        self._configs.pop(target_id, None)

    async def execute(
        self,
        target_id: uuid.UUID,
        command: str,
        timeout: float = 30.0,
    ) -> ShellResult:
        """Run a command on the remote host.

        If no connection exists for the target, auto-connects first.
        If the command fails due to connection loss, attempts one reconnect.

        Args:
            target_id: UUID of the target.
            command: Shell command to execute.
            timeout: Maximum seconds for command execution.

        Returns:
            ShellResult with stdout, stderr, exit_code, timed_out.

        Raises:
            SSHConnectionError: If connect/reconnect fails.
            SSHTargetNotConnectedError: If no config is known for the target.
        """
        # Auto-connect if not connected but config is known
        if target_id not in self._connections:
            config = self._configs.get(target_id)
            if config is None:
                raise SSHTargetNotConnectedError(
                    f"No configuration known for target {target_id}. Call connect() first."
                )
            await self._establish_connection(config)

        try:
            return await self._run_command(target_id, command, timeout)
        except (asyncssh.ConnectionLost, asyncssh.DisconnectError, OSError):
            # Auto-reconnect: attempt once
            config = self._configs.get(target_id)
            if config is None:
                raise SSHConnectionError(
                    f"Connection lost and no config available for target {target_id}"
                )
            self._connections.pop(target_id, None)
            await self._establish_connection(config)
            return await self._run_command(target_id, command, timeout)

    async def _run_command(
        self,
        target_id: uuid.UUID,
        command: str,
        timeout: float,
    ) -> ShellResult:
        """Execute a command on an established connection."""
        conn = self._connections[target_id]
        try:
            result = await asyncio.wait_for(
                conn.run(command, check=False),
                timeout=timeout,
            )
            return ShellResult(
                exit_code=result.exit_status if result.exit_status is not None else -1,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                timed_out=False,
            )
        except asyncio.TimeoutError:
            return ShellResult(
                exit_code=-1,
                stdout="",
                stderr="",
                timed_out=True,
            )

    async def upload(
        self,
        target_id: uuid.UUID,
        local_path: str | Path,
        remote_path: str,
    ) -> None:
        """Transfer a file to the remote host via SFTP.

        Args:
            target_id: UUID of the target.
            local_path: Local file path to upload.
            remote_path: Remote destination path.

        Raises:
            SSHTargetNotConnectedError: If no connection exists.
        """
        conn = self._connections.get(target_id)
        if conn is None:
            raise SSHTargetNotConnectedError(f"Target {target_id} is not connected")

        async with conn.start_sftp_client() as sftp:
            await sftp.put(str(local_path), remote_path)

    async def download(
        self,
        target_id: uuid.UUID,
        remote_path: str,
        local_path: str | Path,
    ) -> None:
        """Transfer a file from the remote host via SFTP.

        Args:
            target_id: UUID of the target.
            remote_path: Remote file path to download.
            local_path: Local destination path.

        Raises:
            SSHTargetNotConnectedError: If no connection exists.
        """
        conn = self._connections.get(target_id)
        if conn is None:
            raise SSHTargetNotConnectedError(f"Target {target_id} is not connected")

        async with conn.start_sftp_client() as sftp:
            await sftp.get(remote_path, str(local_path))

    async def check_liveness(self, target_id: uuid.UUID) -> bool:
        """Test if a connection is alive by running a trivial command.

        Args:
            target_id: UUID of the target.

        Returns:
            True if the connection is alive, False otherwise.
        """
        if target_id not in self._connections:
            return False

        try:
            result = await self._run_command(target_id, "echo ok", timeout=10.0)
            return result.exit_code == 0
        except Exception:
            return False

    async def reconnect(self, target_id: uuid.UUID) -> None:
        """Disconnect then connect again.

        Args:
            target_id: UUID of the target.

        Raises:
            SSHConnectionError: If reconnect fails.
            SSHTargetNotConnectedError: If no config is known for the target.
        """
        config = self._configs.get(target_id)
        if config is None:
            raise SSHTargetNotConnectedError(f"No configuration known for target {target_id}")

        # Disconnect (ignore errors during disconnect)
        conn = self._connections.pop(target_id, None)
        if conn is not None:
            try:
                conn.close()
                await conn.wait_closed()
            except Exception:
                pass

        await self._establish_connection(config)

    async def close_all(self) -> None:
        """Close all active connections."""
        for target_id in list(self._connections.keys()):
            await self.disconnect(target_id)
