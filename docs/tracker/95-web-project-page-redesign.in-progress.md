# Issue #95: Web project page redesign — sessions, issues, and sub-agents

## Problem

The project page currently only shows a flat list of sessions. But a project has more structure:

- **Sessions** — active agent conversations (with sub-agent trees)
- **Issues** — task tracker per project (open/in_progress/closed)

None of this is visible in the web UI. The user can't see what's being worked on, what's queued, or how agents relate to each other.

## Scope

This issue covers the **project page layout redesign** only. It adds tabbed navigation and wires existing backend APIs into the UI. No backend changes needed.

**In scope:**
1. Tabbed layout on the project page (Sessions | Issues)
2. Enhanced session list rows (show sub-agent count, created_at)
3. Issues tab with list, status filter, create form
4. Enhanced session creation dialog (engine, mode, issue link)
5. Frontend API client for issues
6. Tests for new components

**Out of scope (already exist in SessionPage sidebar):**
- Sub-agent tree view (SubAgentTree component exists)
- Tool call timeline (SidebarTabs has this)
- Changed files / diffs panel (SidebarTabs has this)
- Issue detail page (separate issue if needed)

## Dependencies

- None. All backend APIs already exist:
  - `GET /api/projects/{id}/sessions` -- sessions list
  - `GET /api/projects/{id}/issues` -- issues list with optional `?status=` filter
  - `POST /api/projects/{id}/issues` -- create issue
  - `POST /api/projects/{id}/sessions` -- create session (already supports `issue_id`, `engine`, `mode`)
  - `GET /api/sessions/{id}/subagents` -- sub-agent list (for count)

## Requirements

### 1. Tabbed project page layout
- Replace the current single-section layout with tabs: **Sessions** | **Issues**
- Sessions tab is the default active tab
- Tabs persist selection via URL query param or local state (either is fine)
- Project header (name, description, path, archetype) remains above the tabs

### 2. Enhanced session list (Sessions tab)
- Each session row shows: name, status badge, engine, mode, created_at (relative time e.g. "2h ago"), sub-agent count
- Sub-agent count: fetch from `/api/sessions/{id}/subagents` endpoint, show as a small badge (e.g. "3 sub-agents") or omit if zero
- Status badges use existing color scheme from `SessionList.tsx`
- "New Session" button remains at the top of the Sessions tab

### 3. Issues tab
- Create `web/src/api/issues.ts` API client with: `fetchIssues(projectId, status?)`, `createIssue(projectId, {title, description?})`
- Create `web/src/components/IssueList.tsx` component
- List all issues for the project from `GET /api/projects/{id}/issues`
- Each issue row shows: title, status badge (open/in_progress/closed), created_at
- Status filter bar at the top: All | Open | In Progress | Closed (uses `?status=` query param on the API)
- "New Issue" button that opens inline form or modal with title + optional description fields
- Issue status badge colors: open = blue, in_progress = yellow, closed = green

### 4. Enhanced session creation
- Replace the current `prompt()` dialog with a proper form/modal
- Fields: name (required), engine (dropdown: native / claude_code, default: native), mode (dropdown: execution / brainstorm / interview / planning / review, default: execution)
- Optional: link to an existing issue (dropdown populated from project issues)
- The `createSession` API already accepts `engine`, `mode`, and `issue_id`

## Acceptance Criteria

- [ ] Project page renders with two tabs: "Sessions" and "Issues"
- [ ] Sessions tab shows session list with name, status badge, engine, mode, and created_at
- [ ] Sessions tab shows sub-agent count per session (0 shown as nothing, 1+ shown as badge)
- [ ] Issues tab lists issues from the backend API with title, status badge, and created_at
- [ ] Issues tab has a status filter (All / Open / In Progress / Closed) that filters the list
- [ ] Issues tab has a "New Issue" button that creates an issue via the API and adds it to the list
- [ ] Session creation uses a form/modal instead of browser `prompt()`, with engine and mode selection
- [ ] `web/src/api/issues.ts` exists with `fetchIssues` and `createIssue` functions
- [ ] `web/src/components/IssueList.tsx` exists and renders issue data
- [ ] `cd web && npx vitest run` passes with new tests covering the tabbed layout, issues list, and session creation
- [ ] Existing `ProjectPage.test.tsx` tests still pass (updated for new layout)
- [ ] No TypeScript errors: `cd web && npx tsc --noEmit` passes

## Test Scenarios

### Unit: Issues API client
- `fetchIssues` calls the correct endpoint and returns parsed issues
- `fetchIssues` with status filter appends `?status=` query param
- `createIssue` POSTs to the correct endpoint and returns the new issue

### Unit: IssueList component
- Renders list of issues with title, status badge, and created_at
- Empty state shows "No issues" message
- Status filter buttons highlight the active filter
- Clicking a filter calls the callback with the correct status value

### Unit: ProjectPage tabbed layout
- Renders "Sessions" and "Issues" tabs
- Sessions tab is active by default and shows SessionList
- Clicking "Issues" tab shows IssueList
- Project header (name, description, etc.) is visible regardless of active tab

### Unit: Enhanced session creation
- "New Session" button opens the creation form/modal
- Form includes name, engine dropdown, and mode dropdown
- Submitting the form calls createSession with correct parameters
- Form closes after successful creation

### Integration: ProjectPage data loading
- Page loads project, sessions, and switches to issues tab loads issues
- Error state renders correctly if API fails

## Notes

- The backend issue statuses are: `open`, `in_progress`, `closed` (see `IssueUpdate` schema pattern)
- No issues API client exists yet in `web/src/api/` -- must be created
- The `SessionRead` type already has `issue_id` and `parent_session_id` fields
- Keep styling consistent with existing components (Tailwind, same badge patterns)
- This is a single-user self-hosted tool -- no need for permissions UI or multi-user features

## Log

### [SWE] 2026-03-18 11:14
- Created `web/src/api/issues.ts` with `fetchIssues` (supports optional status filter) and `createIssue` functions
- Created `web/src/components/IssueList.tsx` with status filter bar (All/Open/In Progress/Closed), issue creation form, status badges (open=blue, in_progress=yellow, closed=green), and relative time display
- Updated `web/src/pages/ProjectPage.tsx`: replaced flat layout with tabbed layout (Sessions | Issues), replaced browser `prompt()` with proper form including name/engine/mode dropdowns and optional issue link, added issues tab data loading
- Updated `web/src/components/SessionList.tsx`: added relative time display for created_at, added sub-agent count badges (fetched from `/api/sessions/{id}/subagents`)
- Updated `web/src/api/sessions.ts`: added `issue_id` to `createSession` body type
- Files created: `web/src/api/issues.ts`, `web/src/components/IssueList.tsx`, `web/src/test/issues.test.ts`, `web/src/test/IssueList.test.tsx`
- Files modified: `web/src/pages/ProjectPage.tsx`, `web/src/components/SessionList.tsx`, `web/src/api/sessions.ts`, `web/src/test/ProjectPage.test.tsx`
- Tests added: 5 issues API tests, 6 IssueList component tests, 11 ProjectPage tests (rewritten to cover tabs, session form, issue creation)
- Build results: 497 tests pass, 0 fail, TypeScript clean
- Known limitations: issue link dropdown in session form only populates if issues have been loaded (switching to Issues tab first or having issues already fetched)
