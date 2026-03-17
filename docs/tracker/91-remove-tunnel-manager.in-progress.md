# Issue #91: Remove tunnel manager from backend

## Problem

The backend has a tunnel manager (SSH tunnel creation, active tunnels tracking) that was built from the original brainstorm. This is not needed -- the deployment model is:

1. Codehive runs on a remote server (e.g., a VPS)
2. The client (mobile app, web browser, CLI) creates an SSH tunnel to the server: `ssh -L 7433:localhost:7433 myserver`
3. The client connects to `localhost:7433` through the tunnel

The tunnel is a client-side concern, not a backend concern. The backend should not manage tunnels.

## Scope

Remove all tunnel-related code from the backend, web frontend, and tests. No new functionality is added -- this is a pure deletion/cleanup issue.

## Dependencies

None. This is an independent cleanup task.

## Files to Remove

### Backend
- `backend/codehive/execution/tunnel.py` -- TunnelManager, Tunnel dataclass, TunnelStatus enum
- `backend/codehive/core/tunnel.py` -- service layer (create_tunnel, close_tunnel, list_active_tunnels, get_preview_url)
- `backend/codehive/api/routes/tunnels.py` -- API routes (POST/GET/DELETE /api/tunnels)
- `backend/codehive/api/schemas/tunnel.py` -- Pydantic schemas (TunnelCreate, TunnelRead, TunnelPreviewURL)
- `backend/tests/test_tunnels.py` -- all tunnel tests (unit + integration)

### Backend references to update
- `backend/codehive/api/app.py` -- remove `from codehive.api.routes.tunnels import router as tunnels_router` (line 27) and `app.include_router(tunnels_router, dependencies=_auth)` (line 112)

### Web frontend
- `web/src/api/tunnels.ts` -- API client functions
- `web/src/components/TunnelPanel.tsx` -- tunnel UI component
- `web/src/pages/TunnelsPage.tsx` -- tunnels page
- `web/src/test/TunnelPanel.test.tsx` -- TunnelPanel tests
- `web/src/test/TunnelsPage.test.tsx` -- TunnelsPage tests

### Web frontend references to update
- `web/src/App.tsx` -- remove TunnelsPage import (line 10) and route (line 42)
- `web/src/layouts/MainLayout.tsx` -- remove Tunnels nav link (lines 32, 41)
- `web/src/components/sidebar/SidebarTabs.tsx` -- remove "tunnels" tab from TabKey type, tab config, and rendering
- `web/src/test/App.test.tsx` -- remove TunnelsPage import, mock, route, and tunnel-related test cases
- `web/src/test/SidebarTabs.test.tsx` -- remove TunnelPanel mock and tunnel tab test cases

### Mobile
No tunnel-specific screens or code exist in `mobile/src/`. The only tunnel reference is `@expo/ws-tunnel` in `package-lock.json`, which is an Expo internal dependency (not related to our tunnel feature) -- leave it alone.

## Acceptance Criteria

- [ ] `backend/codehive/execution/tunnel.py` is deleted
- [ ] `backend/codehive/core/tunnel.py` is deleted
- [ ] `backend/codehive/api/routes/tunnels.py` is deleted
- [ ] `backend/codehive/api/schemas/tunnel.py` is deleted
- [ ] `backend/tests/test_tunnels.py` is deleted
- [ ] `backend/codehive/api/app.py` no longer imports or registers the tunnels router
- [ ] `web/src/api/tunnels.ts` is deleted
- [ ] `web/src/components/TunnelPanel.tsx` is deleted
- [ ] `web/src/pages/TunnelsPage.tsx` is deleted
- [ ] `web/src/test/TunnelPanel.test.tsx` is deleted
- [ ] `web/src/test/TunnelsPage.test.tsx` is deleted
- [ ] `web/src/App.tsx` has no tunnel imports or routes
- [ ] `web/src/layouts/MainLayout.tsx` has no Tunnels nav link
- [ ] `web/src/components/sidebar/SidebarTabs.tsx` has no tunnel tab
- [ ] Web test files (`App.test.tsx`, `SidebarTabs.test.tsx`) have no tunnel references
- [ ] `cd backend && uv run pytest tests/ -v` passes with 0 tunnel-related tests and no import errors
- [ ] `cd backend && uv run ruff check` passes clean
- [ ] `cd web && npx vitest run` passes with 0 tunnel-related tests and no import errors
- [ ] `grep -ri tunnel backend/codehive/ backend/tests/` returns no results
- [ ] `grep -ri tunnel web/src/` returns no results (except unrelated strings if any)

## Test Scenarios

### Backend: no import errors after deletion
- `uv run python -c "from codehive.api.app import create_app; create_app()"` succeeds without errors
- `uv run pytest tests/ -v` passes -- no test references tunnel modules

### Backend: API routes gone
- Verify `/api/tunnels` is not in the OpenAPI schema (no route registered)

### Web: build succeeds
- `npx vitest run` passes -- no broken imports from deleted tunnel modules
- No TypeScript compilation errors referencing tunnel types

### Web: navigation updated
- SidebarTabs no longer includes a "tunnels" tab
- App router no longer has a `/tunnels` route

## Log

### [SWE] 2026-03-17 20:10
- Deleted all tunnel-related backend files: execution/tunnel.py, core/tunnel.py, api/routes/tunnels.py, api/schemas/tunnel.py, tests/test_tunnels.py
- Deleted all tunnel-related web files: api/tunnels.ts, components/TunnelPanel.tsx, pages/TunnelsPage.tsx, test/TunnelPanel.test.tsx, test/TunnelsPage.test.tsx
- Edited backend/codehive/api/app.py: removed tunnel router import and registration
- Edited web/src/App.tsx: removed TunnelsPage import and /tunnels route
- Edited web/src/layouts/MainLayout.tsx: removed Tunnels nav link
- Edited web/src/components/sidebar/SidebarTabs.tsx: removed TunnelPanel import, "tunnels" from TabKey type, tunnel tab config, and tunnel panel rendering
- Edited web/src/test/App.test.tsx: removed TunnelsPage import, TunnelPanel mock, tunnel route, tunnel page test, and tunnel nav link test
- Edited web/src/test/SidebarTabs.test.tsx: removed TunnelPanel mock and 3 tunnel-specific tests, updated tab count test from 8 to 7
- Files deleted: 10 files
- Files modified: 6 files
- grep -ri tunnel backend/codehive/ backend/tests/ web/src/ returns no results
- Backend: ruff check clean, ruff format clean
- Backend: 1700 tests pass, 8 fail (all pre-existing, unrelated to tunnels), 0 tunnel tests remain
- Web: 96 test files pass, 479 tests pass, 0 tunnel tests remain
- create_app() succeeds without import errors
- Known limitations: none
