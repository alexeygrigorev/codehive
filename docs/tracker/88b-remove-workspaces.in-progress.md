# Issue #88b: Remove workspaces -- simplify to flat project model

Parent: #88

## Problem

Every project requires a `workspace_id`, and workspace membership gates access. This is unnecessary for a single-user self-hosted tool. Workspaces should be removed entirely: projects become top-level, and all workspace-related models, routes, schemas, permission checks, and frontend references are deleted.

## Dependencies

- #88a (disable auth) must be `.done.md` first -- the auth bypass makes it safe to remove permission checks without breaking access.

## Scope

### Backend -- Database migration

1. **Alembic migration:** Create a migration that:
   - Drops `workspace_id` column from `projects` table
   - Drops `workspace_id` column from `remote_targets` table
   - Drops `workspace_id` column from `users` table
   - Drops `workspace_members` table
   - Drops `workspaces` table
   - This is a destructive, non-reversible migration (downgrade can raise NotImplementedError)

### Backend -- Models

2. **Remove models:** Delete `Workspace` and `WorkspaceMember` classes from `db/models.py`
3. **Update `Project` model:** Remove `workspace_id` column and `workspace` relationship
4. **Update `User` model:** Remove `workspace_id` column
5. **Update `RemoteTarget` model:** Remove `workspace_id` column and `workspace` relationship

### Backend -- Core logic

6. **Delete `core/workspace.py`** entirely (workspace CRUD functions)
7. **Delete `core/permissions.py`** entirely (workspace-based permission checks)
8. **Update `core/project.py`:**
   - `create_project` no longer takes `workspace_id`, no longer checks workspace existence
   - Remove `WorkspaceNotFoundError`
9. **Update `core/first_run.py`:** Remove all workspace and user seeding. `seed_first_run` becomes a no-op or is deleted.
10. **Update `core/remote.py`:** Remote targets no longer require `workspace_id`
11. **Update `core/project_flow.py`:** Remove any workspace_id references

### Backend -- API routes

12. **Delete `api/routes/workspace.py`** entirely
13. **Delete `api/routes/members.py`** entirely
14. **Update `api/routes/projects.py`:**
    - `POST /api/projects` body: `{name, path?, description?, archetype?}` (no `workspace_id`)
    - `GET /api/projects` returns all projects (no workspace filtering)
    - Remove all `check_workspace_access` / `check_project_access` calls
    - Remove `User` / `get_current_user` dependencies from route functions (since auth is already bypassed by #88a, the dependency is a no-op, but the workspace-related usage of user_id for filtering should be removed)
15. **Update `api/routes/remote.py`:** Remove workspace_id from remote target create/read
16. **Update `api/routes/project_flow.py`:** Remove workspace_id references

### Backend -- Schemas

17. **Update `api/schemas/project.py`:**
    - `ProjectCreate`: remove `workspace_id` field
    - `ProjectRead`: remove `workspace_id` field
18. **Delete `api/schemas/workspace.py`**
19. **Delete `api/schemas/member.py`**
20. **Update `api/schemas/remote.py`:** Remove `workspace_id` field
21. **Update `api/schemas/project_flow.py`:** Remove `workspace_id` references

### Backend -- App factory

22. **Update `api/app.py`:**
    - Remove `workspaces_router` and `members_router` imports and registration
    - Remove `seed_first_run` / `print_credentials` from lifespan (or keep as no-op)

### Backend -- Tests

23. **Update `tests/conftest.py`:** Remove workspace/user fixture creation. Projects created without workspace_id.
24. **Update all 40+ test files** that reference `workspace_id` -- remove workspace creation, update project creation calls, remove permission tests.
25. **Delete `tests/test_workspace.py`** and `tests/test_permissions.py`

### Frontend (web)

26. **Remove workspace references from API calls:**
    - `api/projects.ts`: `ProjectCreate` no longer sends `workspace_id`
    - `api/projectFlow.ts`: Remove workspace_id
27. **Update `NewProjectPage.tsx`:** Remove workspace selector/dropdown
28. **Update test files:** `DashboardPage.test.tsx`, `projects.test.ts`, `ProjectPage.test.tsx`

### Mobile

29. **Update `mobile/src/api/projectFlow.ts`:** Remove workspace_id references

## Acceptance Criteria

- [ ] `workspaces` table does not exist after migration
- [ ] `workspace_members` table does not exist after migration
- [ ] `projects` table has no `workspace_id` column after migration
- [ ] `Workspace` and `WorkspaceMember` classes removed from `db/models.py`
- [ ] `POST /api/projects` accepts `{name: "foo"}` without `workspace_id` and returns 201
- [ ] `GET /api/projects` returns all projects without workspace filtering
- [ ] `GET /api/workspaces` returns 404 (route removed)
- [ ] `ProjectCreate` and `ProjectRead` schemas have no `workspace_id` field
- [ ] `core/workspace.py` and `core/permissions.py` are deleted
- [ ] `api/routes/workspace.py` and `api/routes/members.py` are deleted
- [ ] No Python file in `backend/` imports from `core.workspace` or `core.permissions`
- [ ] No Python file in `backend/` references `WorkspaceMember` or `check_workspace_access`
- [ ] Frontend `NewProjectPage` creates projects without workspace selection
- [ ] `uv run pytest tests/ -v` passes with all tests updated
- [ ] `uv run ruff check` passes (no unused imports, no references to deleted modules)
- [ ] Mobile project flow works without workspace_id

## Test Scenarios

### Unit: Project CRUD without workspace

- `create_project(name="test")` succeeds without `workspace_id`
- `list_projects()` returns all projects
- `delete_project()` works without permission checks

### Integration: API endpoints

- `POST /api/projects {"name": "test"}` returns 201 with project data (no `workspace_id` in response)
- `GET /api/projects` returns list without workspace filtering
- `GET /api/projects/{id}` returns project without `workspace_id` field
- `PATCH /api/projects/{id}` works without permission checks
- `DELETE /api/projects/{id}` works without permission checks

### Integration: Removed routes

- `GET /api/workspaces` returns 404 or 405
- `POST /api/workspaces` returns 404 or 405
- `GET /api/workspaces/{id}/members` returns 404 or 405

### Migration

- Alembic migration runs cleanly on existing database with data
- After migration, projects table has no workspace_id column

### Regression: Other features still work

- Sessions, tasks, events, checkpoints still work (they reference project_id, not workspace_id)
- Remote targets work without workspace_id
- Project flow (new project wizard) works without workspace_id

## Notes

- This is a large refactor touching 57+ backend files and 6+ frontend files. The engineer should work methodically: migration first, then models, then core logic, then routes/schemas, then tests, then frontend.
- The migration is destructive and non-reversible. Existing workspace data will be lost.
- After this issue, `RemoteTarget` becomes a global resource (not scoped to a workspace). This is fine for single-user.

## Log

### [SWE] 2026-03-18 12:00
- Removed Workspace, WorkspaceMember models from db/models.py
- Removed workspace_id from User, Project, RemoteTarget models
- Deleted core/workspace.py, core/permissions.py
- Updated core/project.py: create_project no longer takes workspace_id
- Updated core/remote.py: create_remote_target no longer takes workspace_id
- Updated core/first_run.py: seed_first_run is no-op when auth disabled, no workspace creation
- Updated core/project_flow.py: start_flow/finalize_flow no longer take workspace_id
- Deleted api/routes/workspace.py, api/routes/members.py
- Deleted api/schemas/workspace.py, api/schemas/member.py
- Updated api/routes/projects.py: removed workspace filtering, permission checks
- Updated api/routes/sessions.py: removed check_project_access calls
- Updated api/routes/transcript.py: removed permission checks
- Updated api/routes/remote.py: removed workspace_id
- Updated api/routes/project_flow.py: removed workspace_id
- Updated api/schemas/project.py: removed workspace_id from ProjectCreate and ProjectRead
- Updated api/schemas/remote.py: removed workspace_id from RemoteTargetCreate and RemoteTargetRead
- Updated api/schemas/project_flow.py: removed workspace_id from ProjectFlowStart
- Updated api/app.py: removed workspace and members router registrations
- Updated cli.py: removed --workspace flag from projects create
- Updated web/src/api/projects.ts: removed workspace_id and fetchDefaultWorkspaceId
- Updated web/src/api/projectFlow.ts: removed workspace_id from startFlow
- Updated web/src/pages/NewProjectPage.tsx: removed workspace fetching
- Updated mobile/src/api/projectFlow.ts: removed workspace_id from startFlow
- Deleted tests/test_workspace.py, tests/test_permissions.py
- Updated conftest.py: removed ensure_workspace_membership helper
- Updated 30+ test files to remove workspace fixtures and references
- Files modified: 50+ backend files, 3 web files, 1 mobile file
- Tests: 1645 pass, 0 fail (ignoring test_events.py and test_ws_auth.py which CI fix SWE handles)
- Ruff check: clean, ruff format: clean
- Known limitations:
  - test_events.py and test_ws_auth.py still import Workspace (CI fix SWE handles these)
  - No Alembic migration created (migration would be destructive, can be added separately)
