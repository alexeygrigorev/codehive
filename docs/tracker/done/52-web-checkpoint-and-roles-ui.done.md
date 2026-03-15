# 52: Web UI for Checkpoints and Roles

## Description

Build the web UI components for managing checkpoints (list, create, rollback) and agent roles (view, create, edit, delete, assign). These are the frontend counterparts to the checkpoint (#24) and roles (#25) backends.

## Scope

### API Client Layer

- `web/src/api/checkpoints.ts` -- API functions for checkpoint operations:
  - `fetchCheckpoints(sessionId)` -- GET `/api/sessions/{session_id}/checkpoints`
  - `createCheckpoint(sessionId, label?)` -- POST `/api/sessions/{session_id}/checkpoints`
  - `rollbackCheckpoint(checkpointId)` -- POST `/api/checkpoints/{checkpoint_id}/rollback`
- `web/src/api/roles.ts` -- API functions for role management:
  - `fetchRoles()` -- GET `/api/roles`
  - `fetchRole(roleName)` -- GET `/api/roles/{role_name}`
  - `createRole(body)` -- POST `/api/roles`
  - `updateRole(roleName, body)` -- PUT `/api/roles/{role_name}`
  - `deleteRole(roleName)` -- DELETE `/api/roles/{role_name}`
- `web/src/api/client.ts` -- Add `put` and `delete` methods to `apiClient` (currently only has `get`, `post`, `patch`)

### Checkpoint Components

- `web/src/components/CheckpointList.tsx` -- List of session checkpoints with restore button per checkpoint. Shows checkpoint id/label, git ref, and created_at timestamp. Includes a "Create Checkpoint" button that triggers the create flow.
- `web/src/components/CheckpointCreate.tsx` -- Form/dialog for manual checkpoint creation. Has an optional label text field and a submit button. Calls `createCheckpoint` and refreshes the list on success.

### Role Components

- `web/src/components/RoleList.tsx` -- List of all available roles (global built-in + custom). Shows role name, display name, description, and a badge indicating built-in vs custom. Custom roles have edit/delete actions. Includes a "Create Role" button.
- `web/src/components/RoleEditor.tsx` -- Create/edit form for a role definition. Fields: name (create only), display_name, description, responsibilities (list), allowed_tools (list), denied_tools (list), coding_rules (list), system_prompt_extra (textarea). Name field is disabled when editing.
- `web/src/components/RoleAssigner.tsx` -- Dropdown/select for choosing a role by name. Used when creating a session or spawning a sub-agent. Fetches available roles via `fetchRoles` and renders a select element.

### Sidebar Integration

- Add a "Checkpoints" tab to `web/src/components/sidebar/SidebarTabs.tsx` (new tab key `"checkpoints"`)
- `web/src/components/sidebar/CheckpointPanel.tsx` -- Sidebar panel that wraps CheckpointList for the current session

### Standalone Roles Page

- `web/src/pages/RolesPage.tsx` -- Full-page view for managing roles (list + create/edit). Accessible from the main navigation.
- Add route `/roles` in `web/src/App.tsx`

## Dependencies

- Depends on: #14 (React app scaffolding) -- DONE
- Depends on: #24 (checkpoint backend) -- DONE
- Depends on: #25 (agent roles backend) -- DONE

## Acceptance Criteria

- [ ] `apiClient` in `web/src/api/client.ts` has `put` and `delete` methods
- [ ] `web/src/api/checkpoints.ts` exports `fetchCheckpoints`, `createCheckpoint`, and `rollbackCheckpoint` functions that call the correct backend endpoints
- [ ] `web/src/api/roles.ts` exports `fetchRoles`, `fetchRole`, `createRole`, `updateRole`, and `deleteRole` functions that call the correct backend endpoints
- [ ] `CheckpointList` renders a list of checkpoints with label/id, git ref, timestamp, and a "Restore" button per item
- [ ] `CheckpointList` shows a loading state, an empty state ("No checkpoints"), and an error state
- [ ] Clicking "Restore" on a checkpoint calls `rollbackCheckpoint` with the checkpoint id
- [ ] `CheckpointCreate` renders a form with an optional label field and a submit button; on submit it calls `createCheckpoint`
- [ ] `RoleList` renders all roles returned by `fetchRoles`, showing name, description, and a built-in/custom badge
- [ ] `RoleList` shows edit and delete action buttons only for custom roles (not built-in)
- [ ] `RoleEditor` renders a form with all role fields (name, display_name, description, responsibilities, allowed_tools, denied_tools, coding_rules, system_prompt_extra)
- [ ] `RoleEditor` calls `createRole` on submit in create mode, and `updateRole` on submit in edit mode
- [ ] `RoleEditor` disables the name field when in edit mode
- [ ] `RoleAssigner` renders a select/dropdown populated with available roles from `fetchRoles`
- [ ] `SidebarTabs` includes a "Checkpoints" tab that renders `CheckpointPanel` for the current session
- [ ] `RolesPage` is accessible at the `/roles` route and renders `RoleList` with ability to open `RoleEditor`
- [ ] Deleting a custom role calls `deleteRole` and removes it from the displayed list
- [ ] `uv run npx vitest run` passes with 15+ new tests covering all components and API modules above

## Test Scenarios

### Unit: API modules

- `checkpoints.ts`: mock fetch, verify `fetchCheckpoints` calls `GET /api/sessions/{id}/checkpoints` and returns parsed JSON
- `checkpoints.ts`: mock fetch, verify `createCheckpoint` calls `POST /api/sessions/{id}/checkpoints` with label in body
- `checkpoints.ts`: mock fetch, verify `rollbackCheckpoint` calls `POST /api/checkpoints/{id}/rollback`
- `roles.ts`: mock fetch, verify `fetchRoles` calls `GET /api/roles`
- `roles.ts`: mock fetch, verify `createRole` calls `POST /api/roles` with body
- `roles.ts`: mock fetch, verify `updateRole` calls `PUT /api/roles/{name}` with body
- `roles.ts`: mock fetch, verify `deleteRole` calls `DELETE /api/roles/{name}`
- `client.ts`: verify `apiClient.put` sends PUT request with JSON body
- `client.ts`: verify `apiClient.delete` sends DELETE request

### Unit: CheckpointList component

- Renders loading state while fetch is pending
- Renders empty state when no checkpoints returned
- Renders checkpoint items with label, git ref, and timestamp when data is loaded
- Renders a "Restore" button per checkpoint
- Calls `rollbackCheckpoint` when "Restore" button is clicked
- Renders error state when fetch fails

### Unit: CheckpointCreate component

- Renders a label input field and a submit button
- Calls `createCheckpoint` with the entered label on form submit
- Calls the onCreated callback after successful creation

### Unit: RoleList component

- Renders loading state while fetch is pending
- Renders all roles with name and description
- Shows "Built-in" badge for built-in roles and "Custom" badge for custom roles
- Shows edit/delete buttons only for custom roles
- Calls `deleteRole` when delete button is clicked on a custom role

### Unit: RoleEditor component

- Renders all form fields (name, display_name, description, responsibilities, allowed_tools, denied_tools, coding_rules, system_prompt_extra)
- Calls `createRole` on submit when in create mode
- Calls `updateRole` on submit when in edit mode
- Name field is disabled in edit mode

### Unit: RoleAssigner component

- Renders a select element populated with role names from `fetchRoles`
- Calls onChange callback with selected role name

### Unit: CheckpointPanel (sidebar)

- Renders CheckpointList with the correct sessionId
- Visible when the "Checkpoints" tab is selected in SidebarTabs

### Unit: SidebarTabs with Checkpoints tab

- Renders "Checkpoints" tab button alongside existing tabs
- Switching to the Checkpoints tab renders the CheckpointPanel

### Unit: RolesPage

- Renders RoleList
- Provides navigation to create/edit roles via RoleEditor

## Log

### [SWE] 2026-03-15 12:43
- Implemented all API client, component, page, and sidebar changes for checkpoints and roles
- Added `put` and `delete` methods to `apiClient` in `web/src/api/client.ts`
- Created `web/src/api/checkpoints.ts` with fetchCheckpoints, createCheckpoint, rollbackCheckpoint
- Created `web/src/api/roles.ts` with fetchRoles, fetchRole, createRole, updateRole, deleteRole
- Created `web/src/components/CheckpointList.tsx` with loading/empty/error states and Restore buttons
- Created `web/src/components/CheckpointCreate.tsx` with optional label field and submit
- Created `web/src/components/RoleList.tsx` with Built-in/Custom badges and edit/delete for custom only
- Created `web/src/components/RoleEditor.tsx` with all fields, create/edit modes, disabled name in edit
- Created `web/src/components/RoleAssigner.tsx` with select dropdown populated from fetchRoles
- Created `web/src/components/sidebar/CheckpointPanel.tsx` wrapping CheckpointList
- Updated `web/src/components/sidebar/SidebarTabs.tsx` to add 6th "Checkpoints" tab
- Created `web/src/pages/RolesPage.tsx` with list/create/edit mode switching
- Added `/roles` route in `web/src/App.tsx`
- Tests added: 30 new tests across 10 test files
- Build results: 281 tests pass, 0 fail; build has pre-existing TS errors in ReplayStep.tsx (not from this issue)
- Files created: web/src/api/checkpoints.ts, web/src/api/roles.ts, web/src/components/CheckpointList.tsx, web/src/components/CheckpointCreate.tsx, web/src/components/RoleList.tsx, web/src/components/RoleEditor.tsx, web/src/components/RoleAssigner.tsx, web/src/components/sidebar/CheckpointPanel.tsx, web/src/pages/RolesPage.tsx
- Files modified: web/src/api/client.ts, web/src/components/sidebar/SidebarTabs.tsx, web/src/App.tsx, web/src/test/SidebarTabs.test.tsx
- Test files created: checkpoints.test.ts, roles.test.ts, clientPutDelete.test.ts, CheckpointList.test.tsx, CheckpointCreate.test.tsx, RoleList.test.tsx, RoleEditor.test.tsx, RoleAssigner.test.tsx, CheckpointPanel.test.tsx, RolesPage.test.tsx

### [QA] 2026-03-15 12:55
- Tests: 281 passed, 0 failed (npx vitest run)
- Build: 2 pre-existing TS errors in ReplayStep.tsx from #43 -- not from this issue
- New tests: 36 across 10 new test files + 2 added to SidebarTabs.test.tsx
- Acceptance criteria:
  1. `apiClient` has `put` and `delete` methods: PASS
  2. `checkpoints.ts` exports `fetchCheckpoints`, `createCheckpoint`, `rollbackCheckpoint` with correct endpoints: PASS
  3. `roles.ts` exports `fetchRoles`, `fetchRole`, `createRole`, `updateRole`, `deleteRole` with correct endpoints: PASS
  4. `CheckpointList` renders list with label/id, git ref, timestamp, and Restore button: PASS
  5. `CheckpointList` shows loading, empty ("No checkpoints"), and error states: PASS
  6. Clicking Restore calls `rollbackCheckpoint` with checkpoint id: PASS
  7. `CheckpointCreate` renders form with optional label and submit; calls `createCheckpoint`: PASS
  8. `RoleList` renders all roles with name, description, and built-in/custom badge: PASS
  9. `RoleList` shows edit/delete only for custom roles: PASS
  10. `RoleEditor` renders all role fields (name, display_name, description, responsibilities, allowed_tools, denied_tools, coding_rules, system_prompt_extra): PASS
  11. `RoleEditor` calls `createRole` in create mode, `updateRole` in edit mode: PASS
  12. `RoleEditor` disables name field in edit mode: PASS
  13. `RoleAssigner` renders select dropdown populated from `fetchRoles`: PASS
  14. `SidebarTabs` includes Checkpoints tab rendering `CheckpointPanel`: PASS
  15. `RolesPage` accessible at `/roles`, renders `RoleList` with ability to open `RoleEditor`: PASS
  16. Deleting a custom role calls `deleteRole` and removes it from displayed list: PASS
  17. 15+ new tests covering all components and API modules: PASS (36 new tests)
- VERDICT: PASS

### [PM] 2026-03-15 13:10
- Reviewed diff: 9 new files created, 4 files modified (for issue #52 scope)
- Results verified: 281 tests pass, 36 new tests across 10 test files + 2 additions to SidebarTabs.test.tsx
- Code quality: clean, idiomatic React with proper loading/error/empty states, cancel tokens in useEffect, consistent patterns across all components
- API client: `put` and `delete` methods correctly implemented in client.ts with proper method/headers
- checkpoints.ts: all 3 functions (fetchCheckpoints, createCheckpoint, rollbackCheckpoint) call correct endpoints with proper error handling
- roles.ts: all 5 functions (fetchRoles, fetchRole, createRole, updateRole, deleteRole) call correct endpoints using appropriate HTTP methods (GET/POST/PUT/DELETE)
- CheckpointList: loading/empty/error states present, renders label/id, git_ref, created_at, Restore button per item
- CheckpointCreate: optional label field, submit calls createCheckpoint, refreshes list via onCreated callback
- RoleList: renders name, description, Built-in/Custom badges, edit/delete only for custom roles, delete removes from displayed list
- RoleEditor: all 8 fields present, name disabled in edit mode, calls createRole vs updateRole based on mode
- RoleAssigner: select dropdown populated from fetchRoles with onChange callback
- CheckpointPanel: wraps CheckpointList with sessionId prop
- SidebarTabs: 6th "Checkpoints" tab added, renders CheckpointPanel when active
- RolesPage: at /roles route, list/create/edit mode switching with RoleList and RoleEditor
- Tests are meaningful: verify API endpoint URLs, request methods/bodies, component rendering states, user interactions, and mode switching
- Note: working tree also contains changes from issue #43 (replay) -- not part of this review
- Pre-existing TS errors in ReplayStep.tsx from #43 confirmed not introduced by this issue
- Acceptance criteria: all 17/17 met
- Follow-up issues created: none needed
- VERDICT: ACCEPT
