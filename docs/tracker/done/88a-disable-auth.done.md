# Issue #88a: Disable auth by default (bypass JWT, skip login)

Parent: #88

## Problem

The app requires JWT login for every API request and shows a login screen on startup. This is unnecessary friction for a self-hosted single-user tool. Auth should be bypassed by default via a config flag, but the code should remain in place for future re-enablement.

## Dependencies

- None (can start immediately)

## Scope

### Backend

1. **Config flag:** Add `auth_enabled: bool = False` to `Settings` (env var `CODEHIVE_AUTH_ENABLED`). Default `False`.

2. **Bypass `get_current_user` dependency:** When `auth_enabled=False`, the dependency should return a sentinel/anonymous user object (or `None`) without checking JWT. All routes that use `Depends(get_current_user)` must work without a token.

3. **Bypass WebSocket auth:** In `api/ws.py`, when `auth_enabled=False`, skip `verify_ws_token` -- accept the connection without requiring a token query param or auth first-message.

4. **Bypass permission checks:** In `core/permissions.py`, when `auth_enabled=False`, `check_workspace_access` and `check_project_access` should return immediately (no-op) instead of checking WorkspaceMember rows. This is a temporary measure until #88b removes workspaces entirely.

5. **Simplify first_run.py:** When `auth_enabled=False`, `seed_first_run` should still create the default workspace (needed until #88b) but skip creating the admin user, password generation, and printing credentials.

6. **Auth routes stay registered** but are simply unused when auth is disabled. No code deletion.

### Frontend (web)

7. **Detect auth mode:** Add a `/api/auth/config` endpoint (public, no auth) that returns `{"auth_enabled": false}`. The frontend calls this on startup.

8. **Skip login:** When `auth_enabled=false`, `AuthProvider` should set `isAuthenticated=true` and `isLoading=false` immediately without checking tokens. `ProtectedRoute` lets everything through.

9. **API client bypass:** When auth is disabled, `client.ts` should not attach `Authorization` headers and should not redirect to `/login` on 401.

10. **Login/Register pages remain** in the codebase but are unreachable when auth is disabled (router skips them or redirects to dashboard).

### Mobile

11. **Skip login screen:** Same pattern as web -- check `/api/auth/config`, skip auth flow when disabled.

### Terminal (TUI)

12. **No changes needed** -- the TUI client does not use JWT auth (it connects to the backend API directly on localhost).

## Acceptance Criteria

- [ ] `CODEHIVE_AUTH_ENABLED` defaults to `false` in `config.py`
- [ ] All API routes return 200 (not 401) without any `Authorization` header when auth is disabled
- [ ] `GET /api/auth/config` returns `{"auth_enabled": false}` (public endpoint, no auth)
- [ ] WebSocket connections succeed without a token when auth is disabled
- [ ] `seed_first_run` does not create admin user or print credentials when auth is disabled
- [ ] When `CODEHIVE_AUTH_ENABLED=true`, all existing auth behavior is preserved (JWT required, login screen, etc.)
- [ ] Frontend navigates directly to dashboard (no login screen) when auth is disabled
- [ ] Frontend API client does not attach `Authorization` headers when auth is disabled
- [ ] Mobile app skips login screen when auth is disabled
- [ ] `uv run pytest tests/ -v` passes -- all existing tests updated for new default
- [ ] No auth-related code is deleted -- only bypassed

## Test Scenarios

### Unit: Auth bypass

- With `auth_enabled=False`: `get_current_user` returns without raising 401
- With `auth_enabled=True`: `get_current_user` raises 401 when no token provided (existing behavior)
- With `auth_enabled=False`: `check_workspace_access` and `check_project_access` return without error
- `GET /api/auth/config` returns correct `auth_enabled` value matching settings

### Integration: API without auth

- With `auth_enabled=False`: `GET /api/projects` returns 200 without `Authorization` header
- With `auth_enabled=False`: `POST /api/projects` returns 201 without `Authorization` header
- With `auth_enabled=False`: WebSocket connects and receives events without token

### Integration: API with auth re-enabled

- With `auth_enabled=True`: `GET /api/projects` returns 401 without `Authorization` header
- With `auth_enabled=True`: Full login flow works (login, get token, use token)

### Frontend

- When `/api/auth/config` returns `auth_enabled=false`, `ProtectedRoute` renders children immediately
- When `/api/auth/config` returns `auth_enabled=true`, `ProtectedRoute` redirects to `/login` if unauthenticated

## Notes

- Do NOT delete any auth code. Wrap bypass logic in `if not settings.auth_enabled:` checks.
- The permission bypass is temporary -- #88b will remove workspaces and permission checks entirely.
- Tests should set `auth_enabled=False` by default (matching the new production default) and have a few explicit `auth_enabled=True` tests to verify auth still works.

## Log

### [SWE] 2026-03-17 20:05
- Implemented auth bypass for all backend and frontend layers
- Backend changes:
  - `config.py`: Added `auth_enabled: bool = False` (env var `CODEHIVE_AUTH_ENABLED`)
  - `api/deps.py`: Added `AnonymousUser` dataclass; `get_current_user` returns `AnonymousUser()` when auth disabled
  - `api/ws.py`: Wrapped WS auth in `if settings.auth_enabled:` block
  - `core/permissions.py`: `check_workspace_access` and `check_project_access` return `None` immediately when auth disabled
  - `core/first_run.py`: When auth disabled, creates default workspace only (no admin user)
  - `api/app.py`: Added `GET /api/auth/config` public endpoint returning `{"auth_enabled": bool}`
- Frontend changes:
  - `api/auth.ts`: Added `fetchAuthConfig()` function
  - `api/client.ts`: Added `isAuthDisabled()`/`setAuthDisabled()` to skip auth headers and 401 handling
  - `context/AuthContext.tsx`: Calls `fetchAuthConfig` on mount; sets `isAuthenticated=true` when auth disabled; exposes `authEnabled` flag
  - `components/ProtectedRoute.tsx`: No changes needed (uses `isAuthenticated` which is now true when auth disabled)
- Mobile changes:
  - `api/client.ts`: Added `checkAuthConfig()`/`isAuthDisabled()` to skip auth headers
  - `App.tsx`: Calls `checkAuthConfig()` on startup
- Tests added: 15 new backend tests (test_auth_bypass.py), 3 new frontend tests (AuthDisabled.test.tsx)
- Existing test files updated with `CODEHIVE_AUTH_ENABLED=true` monkeypatch: test_auth.py, test_permissions.py, test_ws_auth.py, test_first_run.py, test_e2e.py, test_projects.py, test_workspace.py, test_transcript.py, test_error_handling.py
- Build results: Backend 1728 pass, 8 fail (all pre-existing), ruff clean; Frontend 479 pass, 0 fail
- Files modified: backend/codehive/config.py, backend/codehive/api/deps.py, backend/codehive/api/ws.py, backend/codehive/api/app.py, backend/codehive/core/permissions.py, backend/codehive/core/first_run.py, web/src/api/auth.ts, web/src/api/client.ts, web/src/context/AuthContext.tsx, mobile/App.tsx, mobile/src/api/client.ts
- Files created: backend/tests/test_auth_bypass.py, web/src/test/AuthDisabled.test.tsx
- Tests updated: backend/tests/test_auth.py, backend/tests/test_permissions.py, backend/tests/test_ws_auth.py, backend/tests/test_first_run.py, backend/tests/test_e2e.py, backend/tests/test_projects.py, backend/tests/test_workspace.py, backend/tests/test_transcript.py, backend/tests/test_error_handling.py, web/src/test/AuthContext.test.tsx, web/src/test/LoginPage.test.tsx, web/src/test/RegisterPage.test.tsx
- No auth code deleted -- all bypass logic uses `if not settings.auth_enabled:` guards
