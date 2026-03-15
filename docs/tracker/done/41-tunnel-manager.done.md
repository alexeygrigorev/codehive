# 41: Tunnel Manager and Preview Links

## Description
Implement SSH tunnel management for port forwarding and dev server previews. Provide a registry of active tunnels, lifecycle management (create, close, auto-restart), and preview links for forwarded ports. Builds on top of the SSH infrastructure from #40.

The product spec (Phase 10) calls for: "Port forwarding registry, UI: list active tunnels, preview links, restart/close, auto-tunnel for dev server previews."

## Scope

### Execution layer
- `backend/codehive/execution/tunnel.py` -- `TunnelManager` class using asyncssh port forwarding:
  - `create_tunnel(target_id, remote_port, local_port, label)` -- establish a local port forward via the SSH connection from `SSHConnectionManager`, return a `Tunnel` dataclass (id, target_id, remote_port, local_port, label, status, created_at)
  - `close_tunnel(tunnel_id)` -- stop the port forward and remove from registry
  - `close_all_for_target(target_id)` -- close all tunnels for a given remote target
  - `list_tunnels(target_id=None)` -- return all active tunnels, optionally filtered by target_id
  - `get_tunnel(tunnel_id)` -- return a single tunnel by ID or None
  - `get_preview_url(tunnel_id)` -- generate a preview URL (e.g. `http://localhost:{local_port}`) for a tunnel
  - Internal monitoring: detect when a tunnel's SSH connection drops and mark the tunnel as `disconnected`
  - Auto-restart: when `SSHConnectionManager` reconnects a target, attempt to re-establish tunnels that were active for that target
  - Tunnel statuses: `active`, `disconnected`, `closed`
  - Uses the `SSHConnectionManager` from `execution/ssh.py` -- does NOT create its own SSH connections

### Core layer
- `backend/codehive/core/tunnel.py` -- Thin service layer:
  - `create_tunnel(ssh_manager, tunnel_manager, target_id, remote_port, local_port, label)` -- validate the target has an active SSH connection, delegate to `TunnelManager.create_tunnel()`
  - `close_tunnel(tunnel_manager, tunnel_id)` -- delegate to `TunnelManager.close_tunnel()`
  - `list_active_tunnels(tunnel_manager, target_id=None)` -- delegate to `TunnelManager.list_tunnels()`
  - `get_preview_url(tunnel_manager, tunnel_id)` -- delegate to `TunnelManager.get_preview_url()`
  - Error types: `TunnelNotFoundError`, `TunnelTargetNotConnectedError`, `TunnelCreationError`

### API layer
- `backend/codehive/api/schemas/tunnel.py` -- Pydantic schemas: `TunnelCreate`, `TunnelRead`, `TunnelPreviewURL`
- `backend/codehive/api/routes/tunnels.py` -- Endpoints:
  - `POST /api/tunnels` -- create a tunnel (201), body: {target_id, remote_port, local_port, label}
  - `GET /api/tunnels` -- list active tunnels (optional `?target_id=` filter)
  - `GET /api/tunnels/{tunnel_id}` -- get a single tunnel
  - `DELETE /api/tunnels/{tunnel_id}` -- close a tunnel (204)
  - `GET /api/tunnels/{tunnel_id}/preview` -- get preview URL for the tunnel
- Register router in `backend/codehive/api/app.py`

### Frontend
- `web/src/components/TunnelPanel.tsx` -- React component:
  - Lists active tunnels with columns: label, target, remote port, local port, status, preview link
  - "Create Tunnel" button/form (target selector, ports, label)
  - Per-tunnel actions: open preview link, close tunnel
  - Status indicator (active/disconnected/closed)
  - Calls the `/api/tunnels` endpoints

### Tests
- `backend/tests/test_tunnels.py` -- all tests use mocked SSH (no real server or port binding required)

## Dependencies

- Depends on: #40 (SSH connection manager) -- DONE
- Depends on: #14 (React app scaffolding for tunnel UI) -- DONE

## Acceptance Criteria

- [ ] `TunnelManager` class in `backend/codehive/execution/tunnel.py` implements: create_tunnel, close_tunnel, close_all_for_target, list_tunnels, get_tunnel, get_preview_url
- [ ] `TunnelManager` takes an `SSHConnectionManager` instance as a dependency (does not create its own SSH connections)
- [ ] `create_tunnel()` returns a `Tunnel` dataclass with fields: id (UUID), target_id, remote_port, local_port, label, status, created_at
- [ ] Tunnel status transitions: `active` on creation, `disconnected` when SSH connection drops, `closed` when explicitly closed
- [ ] Auto-restart: calling a re-establish method with a target_id attempts to re-create tunnels that were `disconnected` for that target
- [ ] `get_preview_url()` returns a URL string in the format `http://localhost:{local_port}`
- [ ] `close_all_for_target(target_id)` closes all tunnels associated with a specific remote target
- [ ] Service layer in `backend/codehive/core/tunnel.py` with error types: `TunnelNotFoundError`, `TunnelTargetNotConnectedError`, `TunnelCreationError`
- [ ] Core layer validates that the target has an active SSH connection before creating a tunnel
- [ ] Pydantic schemas in `backend/codehive/api/schemas/tunnel.py`: `TunnelCreate`, `TunnelRead`, `TunnelPreviewURL`
- [ ] All 5 API endpoints registered and functional (POST create, GET list, GET detail, DELETE close, GET preview)
- [ ] `POST /api/tunnels` returns 201 with the created tunnel
- [ ] `POST /api/tunnels` returns 400/409 if the target has no active SSH connection
- [ ] `DELETE /api/tunnels/{tunnel_id}` returns 204 and closes the tunnel
- [ ] `GET /api/tunnels/{tunnel_id}/preview` returns the preview URL
- [ ] Tunnel router registered in `app.py` under `create_app()`
- [ ] `web/src/components/TunnelPanel.tsx` renders a list of tunnels with label, target, ports, status, and preview link
- [ ] `TunnelPanel.tsx` has a create-tunnel form and per-tunnel close action
- [ ] `uv run pytest backend/tests/test_tunnels.py -v` passes with 15+ tests
- [ ] All SSH and port-forwarding interactions in tests are mocked (no real SSH server or port binding needed)

## Test Scenarios

### Unit: TunnelManager (`execution/tunnel.py`)
- Create a tunnel with mocked SSH port forwarding, verify it appears in `list_tunnels()` with status `active`
- Create a tunnel, verify the returned `Tunnel` dataclass has all expected fields (id, target_id, remote_port, local_port, label, status, created_at)
- Create a tunnel, then `close_tunnel()`, verify it is removed from `list_tunnels()`
- Create two tunnels for the same target, call `close_all_for_target()`, verify both are removed
- `list_tunnels()` with no tunnels returns empty list
- `list_tunnels(target_id=X)` returns only tunnels for that target
- `get_tunnel(tunnel_id)` returns the tunnel; `get_tunnel(unknown_id)` returns None
- `get_preview_url(tunnel_id)` returns `http://localhost:{local_port}`
- Simulate SSH connection drop: tunnel status changes to `disconnected`
- Auto-restart: after marking tunnels as `disconnected`, call re-establish, verify tunnels are re-created with status `active`
- Create tunnel on target with no active SSH connection, verify error raised

### Unit: Core service layer (`core/tunnel.py`)
- `create_tunnel()` when target has no active connection raises `TunnelTargetNotConnectedError`
- `close_tunnel()` with unknown tunnel_id raises `TunnelNotFoundError`
- `create_tunnel()` with valid connection delegates to TunnelManager and returns tunnel

### Integration: API endpoints (`routes/tunnels.py`)
- `POST /api/tunnels` with mocked SSH connection creates a tunnel, returns 201 with UUID and all fields
- `POST /api/tunnels` without active SSH connection returns 400
- `GET /api/tunnels` returns list of active tunnels
- `GET /api/tunnels?target_id=X` filters by target
- `GET /api/tunnels/{id}` returns tunnel details
- `GET /api/tunnels/{id}` with unknown ID returns 404
- `DELETE /api/tunnels/{id}` closes tunnel, returns 204
- `DELETE /api/tunnels/{id}` with unknown ID returns 404
- `GET /api/tunnels/{id}/preview` returns preview URL

### Component: TunnelPanel.tsx
- Renders with no tunnels, shows empty state
- Renders with tunnel data, shows label, ports, status, preview link
- Create-tunnel form is present with target, port, and label fields

## Out of Scope
- Persistent tunnel storage in the database (tunnels are ephemeral, in-memory only -- persisting to DB can be a follow-up)
- Automatic tunnel creation on SSH connect (only manual creation and auto-restart of previously-active tunnels)
- WebSocket-based real-time tunnel status updates (can be added as a follow-up)

## Log

### [SWE] 2026-03-15 13:22
- Implemented TunnelManager in execution layer with create/close/list/get/preview/mark_disconnected/reestablish methods
- Implemented core service layer with validation and error types (TunnelNotFoundError, TunnelTargetNotConnectedError, TunnelCreationError)
- Implemented Pydantic schemas (TunnelCreate, TunnelRead, TunnelPreviewURL)
- Implemented 5 API endpoints (POST create, GET list, GET detail, DELETE close, GET preview) and registered router in app.py
- Implemented TunnelPanel React component with tunnel list, create form, close action, preview links, status indicators
- Implemented frontend API module (tunnels.ts) with fetchTunnels, createTunnel, closeTunnel, fetchTunnelPreview
- Files created:
  - backend/codehive/execution/tunnel.py
  - backend/codehive/core/tunnel.py
  - backend/codehive/api/schemas/tunnel.py
  - backend/codehive/api/routes/tunnels.py
  - backend/tests/test_tunnels.py
  - web/src/api/tunnels.ts
  - web/src/components/TunnelPanel.tsx
  - web/src/test/TunnelPanel.test.tsx
- Files modified:
  - backend/codehive/api/app.py (added tunnels router)
- Tests added: 28 backend (14 unit TunnelManager, 5 unit core service, 9 integration API), 8 frontend component tests
- Build results: 28 backend tests pass, 8 frontend tests pass, ruff clean
- All SSH/port-forwarding mocked, no real connections needed

### [QA] 2026-03-15 13:30
- Backend tests: 28 passed, 0 failed (test_tunnels.py); 1022 passed full suite
- Frontend tests: 8 passed, 0 failed (TunnelPanel.test.tsx); frontend build succeeds
- Ruff check: clean (0 issues)
- Ruff format: clean (all files already formatted)
- Acceptance criteria:
  1. TunnelManager class implements create_tunnel, close_tunnel, close_all_for_target, list_tunnels, get_tunnel, get_preview_url: PASS
  2. TunnelManager takes SSHConnectionManager as dependency: PASS
  3. create_tunnel() returns Tunnel dataclass with id (UUID), target_id, remote_port, local_port, label, status, created_at: PASS
  4. Tunnel status transitions (active on creation, disconnected on drop, closed on close): PASS
  5. Auto-restart via reestablish_tunnels() re-creates disconnected tunnels as active: PASS
  6. get_preview_url() returns http://localhost:{local_port}: PASS
  7. close_all_for_target() closes all tunnels for a target: PASS
  8. Service layer in core/tunnel.py with TunnelNotFoundError, TunnelTargetNotConnectedError, TunnelCreationError: PASS
  9. Core layer validates target has active SSH connection before creating tunnel: PASS
  10. Pydantic schemas TunnelCreate, TunnelRead, TunnelPreviewURL in api/schemas/tunnel.py: PASS
  11. All 5 API endpoints registered and functional (POST create, GET list, GET detail, DELETE close, GET preview): PASS
  12. POST /api/tunnels returns 201 with created tunnel: PASS
  13. POST /api/tunnels returns 400 if target has no active SSH connection: PASS
  14. DELETE /api/tunnels/{tunnel_id} returns 204 and closes tunnel: PASS
  15. GET /api/tunnels/{tunnel_id}/preview returns preview URL: PASS
  16. Tunnel router registered in app.py under create_app(): PASS
  17. TunnelPanel.tsx renders list of tunnels with label, target, ports, status, preview link: PASS
  18. TunnelPanel.tsx has create-tunnel form and per-tunnel close action: PASS
  19. 28 backend tests pass (>= 15 required): PASS
  20. All SSH/port-forwarding interactions mocked: PASS
- VERDICT: PASS

### [PM] 2026-03-15 14:00
- Reviewed diff: 9 files changed (8 new, 1 modified)
  - backend/codehive/execution/tunnel.py (216 lines) -- TunnelManager with full lifecycle
  - backend/codehive/core/tunnel.py (117 lines) -- service layer with 3 error types
  - backend/codehive/api/schemas/tunnel.py (35 lines) -- Pydantic schemas
  - backend/codehive/api/routes/tunnels.py (120 lines) -- 5 API endpoints
  - backend/tests/test_tunnels.py (454 lines) -- 28 backend tests
  - web/src/api/tunnels.ts (62 lines) -- frontend API module
  - web/src/components/TunnelPanel.tsx (215 lines) -- React component
  - web/src/test/TunnelPanel.test.tsx (163 lines) -- 8 frontend tests
  - backend/codehive/api/app.py -- tunnels router registration (2 lines added)
- Results verified: real test data present in QA log (28 backend, 8 frontend, 1022 full suite, ruff clean)
- Code quality observations:
  - Clean layered architecture: execution -> core -> api, each with clear responsibility
  - TunnelManager properly delegates SSH to SSHConnectionManager (no own connections)
  - Tunnel dataclass uses proper UUID, datetime, and Enum types
  - API uses FastAPI dependency injection correctly (get_tunnel_manager depends on get_ssh_manager)
  - Tests use proper mocking via MagicMock(spec=SSHConnectionManager) -- no real SSH
  - Integration tests use httpx AsyncClient with dependency_overrides -- correct pattern
  - Frontend component handles loading/error/empty states properly with cleanup on unmount
  - Port validation in Pydantic schema (ge=1, le=65535) is a nice touch
- Acceptance criteria: all 20 met
  - 1-7: TunnelManager methods and behavior -- verified in execution/tunnel.py and tests
  - 8-9: Core service layer with error types and validation -- verified in core/tunnel.py
  - 10: Pydantic schemas -- verified in api/schemas/tunnel.py
  - 11-15: API endpoints with correct status codes -- verified in routes/tunnels.py and integration tests
  - 16: Router registration -- verified in app.py diff
  - 17-18: Frontend TunnelPanel with list, form, close action -- verified in TunnelPanel.tsx and component tests
  - 19: 28 backend tests (>= 15 required) -- confirmed
  - 20: All SSH mocked -- confirmed, no real connections
- Follow-up issues created: none needed (all criteria met, no descoping)
- VERDICT: ACCEPT
