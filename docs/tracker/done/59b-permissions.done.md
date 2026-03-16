# 59b: Permissions and Authorization

## Description
Implement a permission system: users belong to workspaces via a membership table with roles, projects inherit access from their workspace, and API endpoints enforce permissions. Currently no routes require authentication -- this issue adds permission enforcement to workspace, project, and session routes.

## Implementation Plan

### 1. Workspace membership model
- Add to `backend/codehive/db/models.py`:
  ```python
  class WorkspaceMember(Base):
      __tablename__ = "workspace_members"
      id: UUID, primary_key
      workspace_id: UUID, FK to workspaces
      user_id: UUID, FK to users
      role: str ("owner" | "admin" | "member" | "viewer")
      created_at: datetime
      __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)
  ```
- Alembic migration for the new table
- Add `relationship` on Workspace and User models to `WorkspaceMember`

### 2. Permission logic
- New file: `backend/codehive/core/permissions.py`
- `ROLE_HIERARCHY = {"owner": 4, "admin": 3, "member": 2, "viewer": 1}`
- `async def check_workspace_access(db, user_id, workspace_id, required_role="viewer")` -- returns the WorkspaceMember row or raises HTTPException(403)
- Role hierarchy: owner > admin > member > viewer
  - **owner**: all operations, can delete workspace, manage all members including other admins
  - **admin**: manage projects, sessions, add/remove members (except owner)
  - **member**: create/edit projects and sessions within the workspace
  - **viewer**: read-only access to workspace, projects, and sessions
- `async def check_project_access(db, user_id, project_id, required_role="viewer")` -- looks up the project's workspace_id, then delegates to check_workspace_access

### 3. Permission dependencies in deps.py
- Add to `backend/codehive/api/deps.py`:
  - `require_workspace_role(workspace_id, role)` -- FastAPI dependency that calls check_workspace_access
  - `require_project_role(project_id, role)` -- FastAPI dependency that calls check_project_access
- These dependencies take `current_user` from `get_current_user` (already implemented in #59a)

### 4. Apply to existing routes
- **Workspace routes** (`/api/workspaces`):
  - POST (create): any authenticated user can create a workspace; creator becomes owner
  - GET list: return only workspaces where user is a member
  - GET/{id}, PATCH/{id}: require workspace member (viewer+)
  - DELETE/{id}: require workspace owner
  - GET/{id}/projects: require workspace member (viewer+)
- **Project routes** (`/api/projects`):
  - POST: require workspace member (member+ role, since member can create)
  - GET list: return only projects in workspaces where user is a member
  - GET/{id}: require project access (viewer+)
  - PATCH/{id}: require project access (member+)
  - DELETE/{id}: require project access (admin+)
- **Session routes** (`/api/projects/{project_id}/sessions`, `/api/sessions`):
  - POST (create): require project access (member+)
  - GET list: require project access (viewer+)
  - GET/{id}, PATCH/{id}, DELETE/{id}: require access to session's project (viewer+ for GET, member+ for PATCH/DELETE)
  - POST pause/resume: require project access (member+)

### 5. Workspace membership management endpoints
- POST `/api/workspaces/{workspace_id}/members` -- add a member (admin+ required)
  - Body: `{user_id, role}` -- cannot assign "owner" role via this endpoint
- GET `/api/workspaces/{workspace_id}/members` -- list members (viewer+ required)
- PATCH `/api/workspaces/{workspace_id}/members/{user_id}` -- update role (admin+ required, cannot change owner)
- DELETE `/api/workspaces/{workspace_id}/members/{user_id}` -- remove member (admin+ required, cannot remove owner)

### 6. Auto-ownership on workspace creation
- When a user creates a workspace via POST /api/workspaces, automatically create a WorkspaceMember row with role="owner" for that user

## Acceptance Criteria

- [ ] `workspace_members` table exists with columns: id, workspace_id, user_id, role, created_at
- [ ] Unique constraint on (workspace_id, user_id) prevents duplicate memberships
- [ ] `backend/codehive/core/permissions.py` exists with `check_workspace_access` and `check_project_access` functions
- [ ] Role hierarchy is enforced: owner > admin > member > viewer
- [ ] Workspace routes require authentication and enforce membership
- [ ] GET /api/workspaces returns only workspaces the authenticated user belongs to (not all workspaces)
- [ ] POST /api/workspaces creates a WorkspaceMember(role="owner") for the creating user
- [ ] DELETE /api/workspaces/{id} returns 403 unless the user is the workspace owner
- [ ] Project routes require authentication; GET /api/projects returns only projects in user's workspaces
- [ ] POST /api/projects requires member+ role in the target workspace; viewers get 403
- [ ] GET /api/projects/{id} for a project in a workspace where user is NOT a member returns 403
- [ ] Session create/pause/resume/delete require member+ role; viewers get 403 on write operations
- [ ] GET /api/workspaces/{id}/members returns the membership list (viewer+ required)
- [ ] POST /api/workspaces/{id}/members adds a member (admin+ required)
- [ ] Unauthenticated requests to protected endpoints return 401
- [ ] `uv run pytest tests/test_permissions.py -v` passes with 15+ tests

## Test Scenarios

### Unit: Role hierarchy logic
- `check_workspace_access(user, ws, "viewer")` succeeds for all roles (owner, admin, member, viewer)
- `check_workspace_access(user, ws, "member")` succeeds for owner, admin, member; fails for viewer
- `check_workspace_access(user, ws, "admin")` succeeds for owner, admin; fails for member, viewer
- `check_workspace_access(user, ws, "owner")` succeeds only for owner
- Non-member user raises 403 for any required role

### Unit: Project access delegation
- `check_project_access(user, project_id, "viewer")` looks up project's workspace and checks membership
- User who is a member of workspace A cannot access projects in workspace B

### Integration: Workspace route protection
- Unauthenticated GET /api/workspaces returns 401
- Authenticated user creates workspace, gets 201, and is auto-assigned as owner
- User A creates workspace; User B (not a member) calls GET /api/workspaces/{id} and gets 403
- User A (owner) deletes workspace, gets 204; User B (admin) tries delete, gets 403

### Integration: Project route protection
- User A (member role) creates project in workspace, gets 201
- User B (viewer role) tries POST /api/projects in same workspace, gets 403
- User B (viewer role) calls GET /api/projects/{id}, gets 200 (read access)
- User C (not a member) calls GET /api/projects/{id}, gets 403

### Integration: Session route protection
- User with member role creates session in project, gets 201
- User with viewer role tries to create session, gets 403
- User with viewer role reads session, gets 200
- Non-member tries to read session, gets 403

### Integration: Membership management
- Owner adds a new member with role "member", gets 201
- Member tries to add another member, gets 403 (not admin)
- Admin changes member's role to "admin", gets 200
- Admin tries to change owner's role, gets 403
- Admin removes a member, gets 204
- Adding duplicate member returns 409

## Out of Scope
- Email invite flow (future issue)
- Per-project access overrides (all access is workspace-level for now)
- API key / service account authentication

## Dependencies
- Depends on: #59a (user model + JWT) -- DONE
- Depends on: #47 (workspace API) -- DONE

## Log

### [SWE] 2026-03-16 14:30
- Implemented full permissions and authorization system for workspace-based access control
- **Model**: Added `WorkspaceMember` model with id, workspace_id, user_id, role, created_at fields and UniqueConstraint on (workspace_id, user_id)
- **Relationships**: Added `members` relationship on Workspace model, `user` relationship on WorkspaceMember
- **Permission logic**: Created `backend/codehive/core/permissions.py` with:
  - `ROLE_HIERARCHY = {"owner": 4, "admin": 3, "member": 2, "viewer": 1}`
  - `check_workspace_access()` -- verifies membership and role level, raises 403
  - `check_project_access()` -- looks up project's workspace, delegates to workspace check
- **Membership endpoints**: Created `backend/codehive/api/routes/members.py`:
  - GET `/api/workspaces/{id}/members` (viewer+)
  - POST `/api/workspaces/{id}/members` (admin+, cannot assign owner)
  - PATCH `/api/workspaces/{id}/members/{user_id}` (admin+, cannot change owner)
  - DELETE `/api/workspaces/{id}/members/{user_id}` (admin+, cannot remove owner)
- **Workspace routes**: Modified to enforce permissions:
  - POST creates workspace + auto-assigns creator as owner
  - GET list returns only user's workspaces (membership filter)
  - GET/PATCH require viewer+ membership
  - DELETE requires owner role
- **Project routes**: Modified to enforce permissions:
  - POST requires member+ in target workspace
  - GET list filters to projects in user's workspaces
  - GET requires viewer+, PATCH requires member+, DELETE requires admin+
- **Session routes**: Modified to enforce permissions:
  - Create requires member+ in project's workspace
  - GET requires viewer+, PATCH/DELETE/pause/resume require member+
- **Migration**: Added Alembic migration `f6a7b8c9d0e1_add_workspace_members.py`
- **Workspace delete**: Updated to delete associated workspace_members before deleting workspace
- **Updated existing tests**: Fixed 14 test files to work with new permission requirements (added workspace_member/project_member fixtures, updated expected status codes for non-member access from 404 to 403)

Files created:
- `backend/codehive/core/permissions.py`
- `backend/codehive/api/schemas/member.py`
- `backend/codehive/api/routes/members.py`
- `backend/codehive/db/migrations/versions/f6a7b8c9d0e1_add_workspace_members.py`
- `backend/tests/test_permissions.py`
- `backend/tests/conftest.py`

Files modified:
- `backend/codehive/db/models.py` (added WorkspaceMember model, relationship on Workspace)
- `backend/codehive/api/app.py` (registered members router)
- `backend/codehive/api/routes/workspace.py` (permission enforcement, auto-ownership)
- `backend/codehive/api/routes/projects.py` (permission enforcement, membership filtering)
- `backend/codehive/api/routes/sessions.py` (permission enforcement)
- `backend/codehive/core/workspace.py` (delete members on workspace delete)
- `backend/tests/test_workspace.py` (updated for 403 on non-member access)
- `backend/tests/test_projects.py` (added workspace_member fixture)
- `backend/tests/test_sessions.py` (added project_member fixture)
- `backend/tests/test_models.py` (added workspace_members to expected tables)
- `backend/tests/test_archetypes.py` (added workspace_id_member fixture)
- `backend/tests/test_knowledge.py` (added workspace_member fixture)
- `backend/tests/test_knowledge_analyzer.py` (added workspace_member fixture)
- `backend/tests/test_modes.py` (added membership in _create_project helper)
- `backend/tests/test_project_flow.py` (added workspace_member fixture)
- `backend/tests/test_subagent.py` (added parent_session_member fixture)
- `backend/tests/test_github_webhook.py` (added project_member fixture)

Tests added: 33 in test_permissions.py (role hierarchy, workspace access, project access, workspace route protection, project route protection, session route protection, membership management)
Build results: 1332 tests pass, 0 fail, ruff clean
Known limitations: None

### [QA] 2026-03-16 15:00
- Tests: 33 passed in test_permissions.py, 1332 passed full suite, 0 failed
- Ruff check: clean (all checks passed)
- Ruff format: clean (207 files already formatted)
- Acceptance criteria:
  1. `workspace_members` table with id, workspace_id, user_id, role, created_at: PASS
  2. UniqueConstraint on (workspace_id, user_id): PASS
  3. `permissions.py` with `check_workspace_access` and `check_project_access`: PASS
  4. Role hierarchy enforced (owner > admin > member > viewer): PASS
  5. Workspace routes require auth and enforce membership: PASS
  6. GET /api/workspaces returns only user's workspaces: PASS
  7. POST /api/workspaces creates WorkspaceMember(role="owner"): PASS
  8. DELETE /api/workspaces/{id} returns 403 unless owner: PASS
  9. Project routes require auth; GET /api/projects filtered by membership: PASS
  10. POST /api/projects requires member+; viewers get 403: PASS
  11. GET /api/projects/{id} returns 403 for non-member: PASS
  12. Session create/pause/resume/delete require member+; viewers get 403 on writes: PASS
  13. GET /api/workspaces/{id}/members returns list (viewer+): PASS
  14. POST /api/workspaces/{id}/members adds member (admin+): PASS
  15. Unauthenticated requests return 401: PASS
  16. 15+ tests in test_permissions.py: PASS (33 tests)
- VERDICT: PASS

### [PM] 2026-03-16 15:30
- Reviewed diff: 19 files changed (+366/-267)
- Results verified: real data present -- 1332 tests pass, 33 permission-specific tests, ruff clean
- All 16 acceptance criteria verified against code and tests:
  1. workspace_members table with correct columns: PASS
  2. UniqueConstraint on (workspace_id, user_id): PASS
  3. permissions.py with check_workspace_access and check_project_access: PASS
  4. Role hierarchy (owner=4 > admin=3 > member=2 > viewer=1): PASS
  5. Workspace routes require auth + membership: PASS
  6. GET /api/workspaces filtered by membership: PASS
  7. POST /api/workspaces auto-creates owner membership: PASS
  8. DELETE /api/workspaces/{id} requires owner role: PASS
  9. Project routes require auth, list filtered by membership: PASS
  10. POST /api/projects requires member+, viewers get 403: PASS
  11. GET /api/projects/{id} returns 403 for non-member: PASS
  12. Session write ops require member+, viewers get 403: PASS
  13. GET members endpoint (viewer+): PASS
  14. POST members endpoint (admin+): PASS
  15. Unauthenticated requests return 401: PASS
  16. 33 tests in test_permissions.py (exceeds 15+ requirement): PASS
- Code quality: clean, well-structured, follows project patterns. Permission logic centralized in permissions.py. Existing tests updated to work with new auth requirements.
- Note: PATCH /api/workspaces/{id} requires only "viewer" role per spec, which allows viewers to modify workspace settings. This matches the written implementation plan but may warrant tightening in a future issue.
- Follow-up issues created: none needed
- VERDICT: ACCEPT
