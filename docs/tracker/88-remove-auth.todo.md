# Issue #88: Remove auth and workspaces — simplify for single-user

## Problem

The app has a full JWT auth system and multi-workspace/multi-user model, but this is a self-hosted single-user tool. Auth adds friction (login screen, token management) and workspaces add unnecessary complexity (every project needs a workspace_id, workspace CRUD, workspace members).

## Requirements

### Auth — disable by default
- [ ] Make auth middleware optional / disabled by default via `CODEHIVE_AUTH_ENABLED=false`
- [ ] Remove or skip JWT token checks on API routes when auth is disabled
- [ ] Remove the login screen from the web frontend — go straight to the dashboard
- [ ] WebSocket connections should work without token when auth is disabled
- [ ] Mobile app should skip the login screen when auth is disabled
- [ ] Keep the auth code in place but bypassed — can be re-enabled later

### Workspaces — remove entirely
- [ ] Remove workspace_id foreign key from projects table (Alembic migration)
- [ ] Remove workspaces and workspace_members tables (migration)
- [ ] Remove workspace API routes (/api/workspaces/*)
- [ ] Remove Workspace, WorkspaceMember models
- [ ] Remove workspace-related permission checks (check_workspace_access)
- [ ] Projects become top-level: POST /api/projects just needs name + optional path/description
- [ ] Update first_run.py — no workspace/user seeding when auth is off
- [ ] Remove workspace references from web and mobile frontends
- [ ] Clean up tests

## Notes

- Breaking DB change — needs Alembic migration
- Don't delete auth code, just bypass with config flag
- The workspace concept can be re-added later if multi-tenancy is needed
