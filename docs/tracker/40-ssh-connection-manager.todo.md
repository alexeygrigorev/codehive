# 40: SSH Connection Manager

## Description
Implement the SSH connection manager for remote server access. Store connection targets (host, key, known_hosts), manage connection lifecycle, and provide liveness checks with auto-reconnect.

## Scope
- `backend/codehive/execution/ssh.py` -- SSH connection manager using asyncssh: connect, execute commands, transfer files, disconnect
- `backend/codehive/core/remote.py` -- Remote target CRUD: store/retrieve SSH connection configs
- `backend/codehive/api/routes/remote.py` -- Endpoints for managing remote targets (add, list, test connection, remove)
- `backend/tests/test_ssh.py` -- SSH connection tests (with mocked SSH server)

## Dependencies
- Depends on: #03 (DB models for storing remote targets)
- Depends on: #08 (execution layer pattern to follow)
