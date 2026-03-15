# 40: SSH Connection Manager

## Description

Implement the SSH connection manager for remote server access. Store connection targets (host, port, username, key path, known_hosts policy), manage connection lifecycle, and provide liveness checks with auto-reconnect. This is the foundation layer that #41 (Tunnel Manager) builds on.

The product spec (Phase 10) calls for: "SSH connection manager (paramiko / asyncssh), store targets: host, key, known_hosts, liveness checks, auto-reconnect."

## Scope

### Database layer
- Add `RemoteTarget` model to `backend/codehive/db/models.py` -- stores SSH connection configurations (id, workspace_id, label, host, port, username, key_path, known_hosts_policy, last_connected_at, status, created_at)
- Add Alembic migration for the `remote_targets` table

### Core layer
- `backend/codehive/core/remote.py` -- Remote target CRUD: create, list, get, update, delete remote targets. Validate required fields (host, username). Prevent deletion of targets that have active connections.

### Execution layer
- `backend/codehive/execution/ssh.py` -- `SSHConnectionManager` class using asyncssh:
  - `connect(target_id)` -- establish SSH connection using stored target config
  - `disconnect(target_id)` -- close an active connection
  - `execute(target_id, command, timeout)` -- run a command on the remote host, return stdout/stderr/exit_code (analogous to `ShellRunner.run()`)
  - `upload(target_id, local_path, remote_path)` -- transfer a file to the remote host via SFTP
  - `download(target_id, remote_path, local_path)` -- transfer a file from the remote host via SFTP
  - `check_liveness(target_id)` -- test if a connection is alive (send keepalive / run trivial command)
  - `reconnect(target_id)` -- disconnect then connect again
  - Connection pool: track active connections by target_id, reuse open connections
  - Auto-reconnect: if a command fails due to connection loss, attempt one reconnect before raising

### API layer
- `backend/codehive/api/schemas/remote.py` -- Pydantic schemas: `RemoteTargetCreate`, `RemoteTargetRead`, `RemoteTargetUpdate`, `SSHCommandRequest`, `SSHCommandResult`, `ConnectionStatus`
- `backend/codehive/api/routes/remote.py` -- Endpoints:
  - `POST /api/remote-targets` -- create a remote target (201)
  - `GET /api/remote-targets` -- list all remote targets
  - `GET /api/remote-targets/{id}` -- get a single target
  - `PUT /api/remote-targets/{id}` -- update a target
  - `DELETE /api/remote-targets/{id}` -- delete a target (400 if active connection)
  - `POST /api/remote-targets/{id}/test` -- test the SSH connection (connect, run `echo ok`, disconnect), return success/failure with error message
  - `POST /api/remote-targets/{id}/execute` -- run a command on the remote target, return stdout/stderr/exit_code
- Register router in `backend/codehive/api/app.py`

### Tests
- `backend/tests/test_ssh.py` -- all tests use mocked SSH (no real server required)

## Dependencies

- Depends on: #03 (DB models -- done)
- Depends on: #08 (execution layer pattern -- done)
- Depended on by: #41 (Tunnel Manager)

## Acceptance Criteria

- [ ] `RemoteTarget` model exists in `backend/codehive/db/models.py` with fields: id (UUID), workspace_id (FK), label, host, port (default 22), username, key_path, known_hosts_policy, last_connected_at, status, created_at
- [ ] Alembic migration creates the `remote_targets` table and runs without error
- [ ] `SSHConnectionManager` in `backend/codehive/execution/ssh.py` implements: connect, disconnect, execute, upload, download, check_liveness, reconnect
- [ ] `SSHConnectionManager.execute()` returns a result object with stdout, stderr, exit_code (matching the `ShellResult` pattern from `execution/shell.py`)
- [ ] Connection pool tracks active connections by target_id and reuses them
- [ ] Auto-reconnect: if execute fails due to connection loss, one reconnect attempt is made before raising
- [ ] CRUD operations in `backend/codehive/core/remote.py`: create, list, get, update, delete
- [ ] All 7 API endpoints registered and functional (POST create, GET list, GET detail, PUT update, DELETE, POST test, POST execute)
- [ ] `POST /api/remote-targets` returns 201 with the created target
- [ ] `POST /api/remote-targets/{id}/test` connects, runs a command, and returns success/failure with timing info
- [ ] `DELETE /api/remote-targets/{id}` returns 400 if the target has an active connection
- [ ] Router registered in `app.py` under `create_app()`
- [ ] `uv run pytest backend/tests/test_ssh.py -v` passes with 12+ tests
- [ ] All SSH interactions in tests are mocked (no real SSH server needed to run the test suite)

## Test Scenarios

### Unit: RemoteTarget CRUD (`core/remote.py`)
- Create a remote target with valid fields, verify it persists in DB
- Create a target with missing required fields (host, username), verify validation error
- List targets for a workspace, verify filtering works
- Get a target by ID, verify fields match
- Update a target's host/port, verify changes persist
- Delete a target, verify it is removed

### Unit: SSHConnectionManager (`execution/ssh.py`)
- Connect to a mocked SSH server, verify connection is stored in the pool
- Execute a command, verify stdout/stderr/exit_code are returned correctly
- Execute with timeout, verify timeout is enforced
- Upload a file via SFTP, verify the mock received the correct data
- Download a file via SFTP, verify the local file is written
- Check liveness on an active connection, verify it returns True
- Check liveness on a dead connection, verify it returns False
- Auto-reconnect: simulate connection drop during execute, verify reconnect is attempted and command succeeds on retry
- Disconnect, verify connection is removed from pool
- Calling execute on a disconnected target auto-connects first

### Integration: API endpoints (`routes/remote.py`)
- `POST /api/remote-targets` creates a target, returns 201 with UUID
- `GET /api/remote-targets` returns a list including the created target
- `GET /api/remote-targets/{id}` returns the target details
- `PUT /api/remote-targets/{id}` updates fields, returns updated target
- `DELETE /api/remote-targets/{id}` removes the target, returns 204
- `POST /api/remote-targets/{id}/test` with mocked SSH returns success status
- `POST /api/remote-targets/{id}/test` with unreachable host returns failure with error message
- `POST /api/remote-targets/{id}/execute` runs a command and returns result
- `DELETE` on a target with active connection returns 400

## Out of Scope (handled by #41)
- SSH tunnel / port forwarding
- Preview links for forwarded ports
- Tunnel UI components

## Log

### [SWE] 2026-03-15 14:30
- Implemented full SSH connection manager with all required layers
- Database: Added RemoteTarget model to models.py with all specified fields (id, workspace_id, label, host, port, username, key_path, known_hosts_policy, last_connected_at, status, created_at)
- Migration: Created Alembic migration b2c3d4e5f6a7 for remote_targets table
- Execution: SSHConnectionManager in execution/ssh.py with connect, disconnect, execute, upload, download, check_liveness, reconnect, close_all. Connection pool by target_id. Auto-reconnect on connection loss. Execute returns ShellResult matching shell.py pattern.
- Core: CRUD in core/remote.py with create, list, get, update, delete. Validation for required fields. Deletion blocked if active connection.
- API: 7 endpoints in routes/remote.py (POST create 201, GET list, GET detail, PUT update, DELETE 204, POST test, POST execute). Router registered in app.py.
- Schemas: RemoteTargetCreate, RemoteTargetRead, RemoteTargetUpdate, SSHCommandRequest, SSHCommandResult, ConnectionStatus in schemas/remote.py
- Added asyncssh dependency
- Files created: codehive/execution/ssh.py, codehive/core/remote.py, codehive/api/schemas/remote.py, codehive/api/routes/remote.py, codehive/db/migrations/versions/b2c3d4e5f6a7_add_remote_targets.py
- Files modified: codehive/db/models.py, codehive/execution/__init__.py, codehive/api/app.py, pyproject.toml
- Tests added: 33 tests in tests/test_ssh.py (11 CRUD unit, 13 SSH manager unit, 9 API integration)
- Build results: 33 tests pass, 0 fail, ruff clean
- All SSH interactions in tests are mocked (no real SSH server needed)
- Known limitations: None

### [QA] 2026-03-15 15:00
- Tests (test_ssh.py): 33 passed, 0 failed
- Tests (full suite): 830 passed, 1 failed (test_models.py::TestBaseMetadata::test_all_tables_registered)
- Ruff check: clean
- Ruff format: clean
- Acceptance criteria:
  1. RemoteTarget model with all required fields: PASS
  2. Alembic migration creates remote_targets table: PASS
  3. SSHConnectionManager implements connect, disconnect, execute, upload, download, check_liveness, reconnect: PASS
  4. SSHConnectionManager.execute() returns ShellResult with stdout, stderr, exit_code: PASS
  5. Connection pool tracks active connections by target_id and reuses them: PASS
  6. Auto-reconnect on connection loss with one retry: PASS
  7. CRUD in core/remote.py (create, list, get, update, delete): PASS
  8. All 7 API endpoints registered and functional: PASS
  9. POST /api/remote-targets returns 201: PASS
  10. POST /api/remote-targets/{id}/test returns success/failure with timing: PASS
  11. DELETE /api/remote-targets/{id} returns 400 if active connection: PASS
  12. Router registered in app.py under create_app(): PASS
  13. 12+ tests passing: PASS (33 tests)
  14. All SSH interactions mocked: PASS
- VERDICT: FAIL
- Issue: Adding RemoteTarget model to models.py broke existing test `tests/test_models.py::TestBaseMetadata::test_all_tables_registered` which has a hardcoded set of expected table names. The set does not include `remote_targets`. Fix: add `"remote_targets"` to the expected set in that test.

### [SWE] 2026-03-15 15:10
- Fixed tester feedback: added `"remote_targets"` to the expected table names set in `tests/test_models.py::TestBaseMetadata::test_all_tables_registered`
- Files modified: backend/tests/test_models.py
- Build results: 831 tests pass, 0 fail
- Known limitations: None

### [QA] 2026-03-15 15:20
- Tests (full suite): 831 passed, 0 failed
- Ruff check: clean
- Ruff format: clean
- Re-check of previous failure:
  - test_models.py::TestBaseMetadata::test_all_tables_registered now includes `remote_targets`: PASS
- Acceptance criteria (all previously passing, re-confirmed):
  1. RemoteTarget model with all required fields: PASS
  2. Alembic migration creates remote_targets table: PASS
  3. SSHConnectionManager implements connect, disconnect, execute, upload, download, check_liveness, reconnect: PASS
  4. SSHConnectionManager.execute() returns ShellResult with stdout, stderr, exit_code: PASS
  5. Connection pool tracks active connections by target_id and reuses them: PASS
  6. Auto-reconnect on connection loss with one retry: PASS
  7. CRUD in core/remote.py (create, list, get, update, delete): PASS
  8. All 7 API endpoints registered and functional: PASS
  9. POST /api/remote-targets returns 201: PASS
  10. POST /api/remote-targets/{id}/test returns success/failure with timing: PASS
  11. DELETE /api/remote-targets/{id} returns 400 if active connection: PASS
  12. Router registered in app.py under create_app(): PASS
  13. 12+ tests passing: PASS (33 tests in test_ssh.py)
  14. All SSH interactions mocked: PASS
- VERDICT: PASS

### [PM] 2026-03-15 15:45
- Reviewed diff: 11 files changed (6 new, 5 modified)
  - New: execution/ssh.py, core/remote.py, api/routes/remote.py, api/schemas/remote.py, db/migrations/versions/b2c3d4e5f6a7_add_remote_targets.py, tests/test_ssh.py
  - Modified: db/models.py, execution/__init__.py, api/app.py, tests/test_models.py, pyproject.toml
- Results verified: 33/33 tests pass in test_ssh.py, ruff clean, previously-broken test_models test now passes
- Acceptance criteria: all 14 met
  1. RemoteTarget model with all specified fields: MET
  2. Alembic migration creates remote_targets table: MET
  3. SSHConnectionManager implements all 7 methods: MET
  4. execute() returns ShellResult with stdout/stderr/exit_code: MET
  5. Connection pool tracks by target_id, reuses connections: MET
  6. Auto-reconnect on ConnectionLost/DisconnectError/OSError: MET
  7. CRUD in core/remote.py (create, list, get, update, delete): MET
  8. All 7 API endpoints registered and functional: MET
  9. POST /api/remote-targets returns 201: MET
  10. POST test endpoint returns success/failure with timing: MET
  11. DELETE returns 400 if active connection: MET
  12. Router registered in app.py: MET
  13. 12+ tests passing (33 actual): MET
  14. All SSH interactions mocked: MET
- Code quality: Clean layer separation (db/core/execution/api), proper error types, async throughout, tests cover edge cases (timeout, reconnect, dead liveness, delete-while-active)
- Follow-up issues created: none needed
- VERDICT: ACCEPT
