# 15: Web Project Dashboard

## Description

Build the project list and per-project dashboard pages in the web app. Show all projects with their active sessions, recent issues, and status indicators. Replace the current stub `DashboardPage` and `ProjectPage` with functional components that fetch data from the backend API.

## Scope

- `web/src/api/projects.ts` -- API functions for fetching projects (`GET /api/projects`, `GET /api/projects/{id}`)
- `web/src/api/sessions.ts` -- API function for fetching sessions per project (`GET /api/projects/{id}/sessions`)
- `web/src/components/ProjectCard.tsx` -- Project summary card: name, description, archetype, session count, status indicator
- `web/src/components/SessionList.tsx` -- List of sessions within a project, showing name, status, mode, engine, created_at
- `web/src/pages/DashboardPage.tsx` -- Replace stub; fetch and display all projects as a grid/list of `ProjectCard` components; handle loading and error states; link each card to `/projects/{id}`
- `web/src/pages/ProjectPage.tsx` -- Replace stub; fetch project details + sessions; show project header (name, description, archetype, path) and `SessionList`; handle loading, error, and not-found states

### Out of Scope

- Project create/edit/delete UI (future issue)
- Session create UI (future issue)
- WebSocket real-time updates (issue #18)
- Issue listing within projects (depends on issue tracker API, issue #46)

## Dependencies

- Depends on: #14 (React app scaffolding) -- DONE
- Depends on: #04 (project CRUD API) -- DONE
- Depends on: #05 (session CRUD API) -- DONE

## Backend API Reference

These endpoints already exist and are the data sources for this issue:

- `GET /api/projects` returns `ProjectRead[]` -- fields: `id`, `workspace_id`, `name`, `path`, `description`, `archetype`, `knowledge`, `created_at`
- `GET /api/projects/{id}` returns `ProjectRead`
- `GET /api/projects/{id}/sessions` returns `SessionRead[]` -- fields: `id`, `project_id`, `issue_id`, `parent_session_id`, `name`, `engine`, `mode`, `status`, `config`, `created_at`

The existing `apiClient` in `web/src/api/client.ts` provides a `get(path)` method that returns `fetch` Promises against `VITE_API_BASE_URL` (default `http://localhost:8000`).

## Acceptance Criteria

- [ ] `DashboardPage` fetches from `GET /api/projects` on mount and renders a `ProjectCard` for each project
- [ ] Each `ProjectCard` displays the project name, description (truncated if long), archetype badge (if set), and a count of active sessions
- [ ] Each `ProjectCard` links to `/projects/{projectId}` via react-router
- [ ] `DashboardPage` shows a loading indicator while the API call is in progress
- [ ] `DashboardPage` shows an error message if the API call fails
- [ ] `DashboardPage` shows an empty state message when there are zero projects
- [ ] `ProjectPage` fetches project details from `GET /api/projects/{id}` and sessions from `GET /api/projects/{id}/sessions` on mount
- [ ] `ProjectPage` displays project name, description, archetype, and path in a header section
- [ ] `ProjectPage` renders a `SessionList` showing all sessions for the project
- [ ] `SessionList` displays each session's name, status (with a visual indicator such as color or icon), mode, and engine
- [ ] `SessionList` shows an empty state when the project has no sessions
- [ ] Each session row in `SessionList` links to `/sessions/{sessionId}`
- [ ] `ProjectPage` shows a loading indicator while data is loading
- [ ] `ProjectPage` shows a not-found or error state if the project ID is invalid
- [ ] `web/src/api/projects.ts` exports `fetchProjects()` and `fetchProject(id)` functions that use `apiClient`
- [ ] `web/src/api/sessions.ts` exports `fetchSessions(projectId)` function that uses `apiClient`
- [ ] All new components have TypeScript interfaces/types for their props
- [ ] `cd web && npx vitest run` passes with 12+ tests (6 existing + 6+ new)

## Test Scenarios

### Unit: API functions (`web/src/test/projects.test.ts`, `web/src/test/sessions.test.ts`)

- `fetchProjects()` calls `GET /api/projects` and returns parsed project array
- `fetchProjects()` throws on non-ok response
- `fetchProject(id)` calls `GET /api/projects/{id}` and returns parsed project
- `fetchProject(id)` throws on 404
- `fetchSessions(projectId)` calls `GET /api/projects/{projectId}/sessions` and returns parsed session array
- `fetchSessions(projectId)` throws on non-ok response

### Unit: ProjectCard (`web/src/test/ProjectCard.test.tsx`)

- Renders project name and description
- Renders archetype badge when archetype is set
- Does not render archetype badge when archetype is null
- Links to the correct `/projects/{id}` route
- Displays session count when provided

### Unit: SessionList (`web/src/test/SessionList.test.tsx`)

- Renders a row for each session with name, status, mode
- Shows empty state message when sessions array is empty
- Each session row links to `/sessions/{id}`
- Displays status with appropriate visual differentiation (e.g., "idle" vs "executing" vs "completed")

### Integration: DashboardPage (`web/src/test/DashboardPage.test.tsx`)

- Renders loading state initially
- Fetches projects and renders ProjectCard for each
- Shows empty state when API returns empty array
- Shows error state when API call fails
- Clicking a ProjectCard navigates to `/projects/{id}`

### Integration: ProjectPage (`web/src/test/ProjectPage.test.tsx`)

- Renders loading state initially
- Fetches project + sessions and renders project header and SessionList
- Shows error/not-found when project ID does not exist (API returns 404)
- Renders session list with correct data from API

## Implementation Notes

- Use `useState` + `useEffect` for data fetching (no external state management needed yet)
- Reuse the existing `apiClient.get()` from `web/src/api/client.ts`; extend it with a generic JSON helper or add `post`/`patch`/`delete` only if needed
- Session status values from the backend: `idle`, `planning`, `executing`, `waiting_input`, `waiting_approval`, `blocked`, `completed`, `failed`
- Use Tailwind CSS classes consistent with the existing stub pages (e.g., `text-2xl font-bold`, `text-gray-600`)

## Log

### [SWE] 2026-03-15 08:53
- Implemented all 6 files from scope plus updated 1 existing test file
- Created API layer: `web/src/api/projects.ts` (fetchProjects, fetchProject) and `web/src/api/sessions.ts` (fetchSessions), all using apiClient.get() with proper error handling
- Created `web/src/components/ProjectCard.tsx` with name, truncated description, archetype badge, session count, link to /projects/{id}
- Created `web/src/components/SessionList.tsx` with per-session rows showing name, status (color-coded badge), mode, engine, link to /sessions/{id}, empty state
- Replaced stub `web/src/pages/DashboardPage.tsx` with functional component: fetches projects + session counts, renders ProjectCard grid, loading/error/empty states
- Replaced stub `web/src/pages/ProjectPage.tsx` with functional component: fetches project + sessions in parallel, renders header (name, description, archetype, path) + SessionList, loading/error/not-found states
- Updated `web/src/test/App.test.tsx` line 35: changed assertion from checking projectId text to checking loading state (since ProjectPage now fetches data asynchronously)
- Tests added: 26 new tests across 6 test files (projects API: 4, sessions API: 2, ProjectCard: 7, SessionList: 4, DashboardPage: 5, ProjectPage: 4)
- Build results: 35 tests pass, 0 fail, TypeScript build clean
- Files created: web/src/api/projects.ts, web/src/api/sessions.ts, web/src/components/ProjectCard.tsx, web/src/components/SessionList.tsx, web/src/test/projects.test.ts, web/src/test/sessions.test.ts, web/src/test/ProjectCard.test.tsx, web/src/test/SessionList.test.tsx, web/src/test/DashboardPage.test.tsx, web/src/test/ProjectPage.test.tsx
- Files modified: web/src/pages/DashboardPage.tsx, web/src/pages/ProjectPage.tsx, web/src/test/App.test.tsx

### [QA] 2026-03-15 09:10
- Tests: 35 passed, 0 failed (`cd web && npx vitest run`)
- Build: clean (`cd web && npm run build` -- no errors, no warnings)
- Acceptance criteria:
  1. DashboardPage fetches projects on mount, renders ProjectCard per project: PASS
  2. ProjectCard displays name, truncated description, archetype badge, session count: PASS
  3. ProjectCard links to /projects/{projectId}: PASS
  4. DashboardPage shows loading indicator: PASS
  5. DashboardPage shows error message on API failure: PASS
  6. DashboardPage shows empty state for zero projects: PASS
  7. ProjectPage fetches project details + sessions on mount: PASS
  8. ProjectPage displays name, description, archetype, path in header: PASS
  9. ProjectPage renders SessionList: PASS
  10. SessionList displays name, status (color-coded badge), mode, engine: PASS
  11. SessionList shows empty state when no sessions: PASS
  12. Each session row links to /sessions/{sessionId}: PASS
  13. ProjectPage shows loading indicator: PASS
  14. ProjectPage shows not-found/error state for invalid project ID: PASS
  15. projects.ts exports fetchProjects() and fetchProject(id) using apiClient: PASS
  16. sessions.ts exports fetchSessions(projectId) using apiClient: PASS
  17. All new components have TypeScript interfaces/types for props: PASS
  18. vitest run passes with 12+ tests (35 total: 9 existing + 26 new): PASS
- Code quality notes:
  - Type hints used throughout (TypeScript interfaces for all props and API responses)
  - Proper error handling with loading/error/empty states in all pages
  - useEffect cleanup with cancelled flag to prevent state updates on unmounted components
  - Consistent Tailwind CSS styling matching existing patterns
  - No hardcoded values; API base URL comes from env config via apiClient
- VERDICT: PASS

### [PM] 2026-03-15 09:20
- Reviewed diff: 13 files changed (3 modified, 10 new) in web/ directory
- Results verified: tests run independently confirmed 35 pass, build clean (tsc + vite, 34 modules, no warnings)
- Acceptance criteria: all 18 met
  1. DashboardPage fetches /api/projects on mount, renders ProjectCard grid: VERIFIED in code and DashboardPage.test.tsx
  2. ProjectCard shows name, truncated description (120 char cutoff), archetype badge, session count: VERIFIED in component and 7 unit tests
  3. ProjectCard links to /projects/{id} via react-router Link: VERIFIED
  4. DashboardPage loading state ("Loading projects..."): VERIFIED
  5. DashboardPage error state (red text with error message): VERIFIED
  6. DashboardPage empty state ("No projects yet"): VERIFIED
  7. ProjectPage fetches project + sessions via Promise.all on mount: VERIFIED
  8. ProjectPage header shows name, description, archetype badge, path: VERIFIED in code and ProjectPage.test.tsx
  9. ProjectPage renders SessionList component: VERIFIED
  10. SessionList shows name, color-coded status badge (8 status values mapped), mode, engine: VERIFIED
  11. SessionList empty state ("No sessions for this project."): VERIFIED
  12. Session rows link to /sessions/{sessionId}: VERIFIED
  13. ProjectPage loading state ("Loading project..."): VERIFIED
  14. ProjectPage error/not-found state with "Back to Dashboard" link: VERIFIED
  15. projects.ts exports fetchProjects() and fetchProject(id) using apiClient.get(): VERIFIED
  16. sessions.ts exports fetchSessions(projectId) using apiClient.get(): VERIFIED
  17. TypeScript interfaces for all props and API types (ProjectRead, SessionRead, ProjectCardProps, SessionListProps): VERIFIED
  18. vitest passes with 35 tests (9 existing + 26 new, well above 12 minimum): VERIFIED
- Code quality assessment:
  - Proper useEffect cleanup with cancelled flag prevents state updates after unmount
  - Error handling is comprehensive (try/catch with meaningful error messages)
  - API layer correctly uses existing apiClient.get() pattern from client.ts
  - Tailwind CSS styling is consistent with existing stub pages
  - No over-engineering: simple useState + useEffect, no unnecessary abstractions
  - Session status color mapping covers all 8 backend status values from the spec
- Follow-up issues created: none needed
- VERDICT: ACCEPT
