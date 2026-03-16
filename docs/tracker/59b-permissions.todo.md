# 59b: Permissions and Authorization

## Description
Implement a permission system: users belong to workspaces, projects have access control, and API endpoints enforce permissions.

## Implementation Plan

### 1. Workspace membership model
- Add to `backend/codehive/db/models.py`:
  ```
  class WorkspaceMember(Base):
      __tablename__ = "workspace_members"
      id: UUID, primary_key
      workspace_id: UUID, FK to workspaces
      user_id: UUID, FK to users
      role: str ("owner" | "admin" | "member" | "viewer")
      created_at: datetime
  ```
- Alembic migration

### 2. Permission logic
- `backend/codehive/core/permissions.py`
- `async def check_workspace_access(db, user_id, workspace_id, required_role)` -- raises 403 if insufficient
- Role hierarchy: owner > admin > member > viewer
  - **owner**: all operations, can delete workspace, manage members
  - **admin**: manage projects, sessions, members (except owner)
  - **member**: create/edit projects and sessions
  - **viewer**: read-only access
- `async def check_project_access(db, user_id, project_id, required_role)` -- checks via project's workspace

### 3. Permission dependencies
- `backend/codehive/api/deps.py` -- add permission-checking dependencies
- `require_workspace_member(workspace_id)` -- any role
- `require_workspace_admin(workspace_id)` -- admin or owner
- `require_project_access(project_id, role)` -- check via project's workspace

### 4. Apply to routes
- Project routes: require workspace membership
- Session routes: require workspace membership
- Workspace management: require workspace admin
- User management: require admin for managing others, self-service for own profile

### 5. Admin setup
- First registered user is automatically workspace owner
- Workspace owners can invite users (future: email invite flow)

## Acceptance Criteria

- [ ] `workspace_members` table exists with workspace_id, user_id, role
- [ ] Users can only access projects in workspaces they are members of
- [ ] Viewers can read but not create/edit projects or sessions
- [ ] Members can create and edit projects and sessions
- [ ] Admins can manage workspace members
- [ ] Owners can delete workspaces and manage all members
- [ ] Accessing a project in another workspace returns 403
- [ ] First registered user is auto-assigned as workspace owner
- [ ] `uv run pytest tests/test_permissions.py -v` passes with 8+ tests

## Test Scenarios

### Unit: Permission checks
- User is workspace member, verify access granted
- User is NOT workspace member, verify 403
- Viewer tries to create project, verify 403
- Member creates project, verify success
- Admin manages members, verify success

### Integration: Route protection
- User A creates project in workspace 1
- User B (not in workspace 1) tries GET /api/projects/{id}, verify 403
- User B is added to workspace 1 as viewer
- User B tries GET /api/projects/{id}, verify 200
- User B tries POST /api/projects, verify 403 (viewer)

### Unit: Role hierarchy
- Verify owner has all permissions
- Verify admin has member permissions but not owner-only
- Verify member has viewer permissions plus create/edit

## Dependencies
- Depends on: #59a (user model + JWT), #47 (workspace API)
