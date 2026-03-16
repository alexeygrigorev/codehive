# 70: Mobile Issues List

## Description
Add an issues list screen to the mobile app showing issues per project, with status badges and navigation to issue detail. Users tap a project on the dashboard, then navigate to its issues list (alongside the existing sessions list). This leverages the issue tracker API from #46.

## Scope
- `mobile/src/api/issues.ts` -- API client functions for listing issues per project and getting a single issue
- `mobile/src/components/IssueCard.tsx` -- Pressable list item showing issue title, status badge, and created_at timestamp
- `mobile/src/components/IssueStatusBadge.tsx` -- Status badge for issue statuses (open/in_progress/closed), distinct from the existing SessionStatus-based StatusBadge
- `mobile/src/screens/ProjectIssuesScreen.tsx` -- FlatList of issues for a given project, with pull-to-refresh and empty state
- `mobile/src/navigation/types.ts` -- Add `ProjectIssues` route to `DashboardStackParamList`
- `mobile/src/navigation/RootNavigator.tsx` -- Register `ProjectIssuesScreen` in the Dashboard stack navigator
- `mobile/src/screens/ProjectSessionsScreen.tsx` -- Add a button/link to navigate to the project's issues list (or add it from the ProjectSessions screen header)
- `mobile/__tests__/` -- Tests for the new components and screen

## Implementation Notes

### API Client (`api/issues.ts`)
Follow the same pattern as `api/projects.ts` and `api/sessions.ts`:
- `listIssues(projectId: string, status?: string)` -- calls `GET /api/projects/{projectId}/issues` with optional `?status=` query param
- `getIssue(issueId: string)` -- calls `GET /api/issues/{issueId}`

### Issue Status Badge (`components/IssueStatusBadge.tsx`)
Issue statuses differ from session statuses. The valid values are:
- `open` -- blue dot (#2196F3)
- `in_progress` -- yellow/amber dot (#FFC107)
- `closed` -- green dot (#4CAF50)

Use the same visual pattern as the existing `StatusBadge` component (colored dot + label text) but with a separate `IssueStatus` type.

### Issue Card (`components/IssueCard.tsx`)
Follow the `SessionCard` pattern:
- Props: `id`, `title`, `status` (IssueStatus), `createdAt` (string), `onPress`
- Displays: issue title, IssueStatusBadge, human-readable created_at timestamp
- Pressable with ripple/opacity feedback

### Project Issues Screen (`screens/ProjectIssuesScreen.tsx`)
Follow the `ProjectSessionsScreen` pattern exactly:
- Receives `projectId` and `projectName` via route params
- Sets the navigation header title to the project name
- Calls `listIssues(projectId)` on mount
- Renders a FlatList with IssueCard items
- Pull-to-refresh via RefreshControl
- Loading spinner on initial fetch
- Empty state message: "No issues yet"
- By default shows all issues (no status filter); optionally can add a simple filter toggle for open/closed later

### Navigation
- Add `ProjectIssues: { projectId: string; projectName: string }` to `DashboardStackParamList` in `types.ts`
- Register the screen in `DashboardStackNavigator` in `RootNavigator.tsx`
- Add navigation from `ProjectSessionsScreen` to `ProjectIssuesScreen` (e.g., a "View Issues" button in the header or a simple link at the top of the sessions list)

### Navigating to Issue Detail
For this issue, tapping an IssueCard can be a no-op or navigate to a placeholder. A full issue detail screen is out of scope (follow-up issue). The `onPress` prop should be wired but can log or do nothing for now.

## Dependencies
- Depends on: #53b (mobile dashboard with project list and navigation stack) -- must be `.done.md`
- Depends on: #46 (issue tracker API with GET /api/projects/{project_id}/issues endpoint) -- must be `.done.md`

## Acceptance Criteria

- [ ] `mobile/src/api/issues.ts` exports `listIssues(projectId)` that calls `GET /api/projects/{projectId}/issues` and returns the response data
- [ ] `mobile/src/api/issues.ts` exports `getIssue(issueId)` that calls `GET /api/issues/{issueId}` and returns the response data
- [ ] `IssueStatusBadge` renders a blue dot for `open`, yellow dot for `in_progress`, and green dot for `closed`
- [ ] `IssueCard` displays the issue title, an `IssueStatusBadge`, and a human-readable created_at timestamp
- [ ] `IssueCard` is pressable (accepts and calls `onPress` callback)
- [ ] `ProjectIssuesScreen` calls `listIssues(projectId)` on mount and renders a FlatList of issues
- [ ] `ProjectIssuesScreen` shows a loading spinner during initial fetch
- [ ] `ProjectIssuesScreen` supports pull-to-refresh via `RefreshControl`
- [ ] `ProjectIssuesScreen` shows "No issues yet" empty state when the API returns an empty list
- [ ] `ProjectIssuesScreen` sets the navigation header title to the project name
- [ ] `DashboardStackParamList` in `types.ts` includes `ProjectIssues: { projectId: string; projectName: string }`
- [ ] `ProjectIssuesScreen` is registered in the Dashboard stack navigator in `RootNavigator.tsx`
- [ ] There is a way to navigate from `ProjectSessionsScreen` to `ProjectIssuesScreen` for the same project (e.g., header button or in-list link)
- [ ] No TypeScript errors: `npx tsc --noEmit` in `mobile/` passes
- [ ] `npx jest` in `mobile/` passes with 8+ new tests covering the new components and screen

## Test Scenarios

### Unit: IssueStatusBadge
- Render with status `open`, verify the dot color is blue (#2196F3) and label text is "open"
- Render with status `in_progress`, verify the dot color is yellow (#FFC107) and label text is "in_progress"
- Render with status `closed`, verify the dot color is green (#4CAF50) and label text is "closed"

### Unit: IssueCard
- Render with mock issue data `{ id: "i1", title: "Fix login bug", status: "open", createdAt: "2026-03-15T10:00:00Z" }`, verify the title "Fix login bug" is displayed, an IssueStatusBadge is present, and a timestamp is shown
- Render IssueCard and simulate press, verify `onPress` callback is called

### Integration: ProjectIssuesScreen
- Mock `listIssues` to return 2 issues, render ProjectIssuesScreen with route params, verify both issue titles appear in the FlatList
- Mock `listIssues` to return an empty array, verify the "No issues yet" empty state message is shown
- Mock `listIssues` to return 1 issue, verify loading spinner is shown initially and then replaced by the list

### Integration: Navigation to Issues
- Render ProjectSessionsScreen, verify a navigation element (button/link) to view project issues is present
- Verify `DashboardStackParamList` includes `ProjectIssues` route with correct params type

### API: issues module
- Verify `listIssues` calls the correct endpoint `/api/projects/{projectId}/issues`
- Verify `getIssue` calls the correct endpoint `/api/issues/{issueId}`

## Log

### [SWE] 2026-03-16 12:00
- Implemented all scope items for mobile issues list feature
- Created `mobile/src/api/issues.ts` with `listIssues(projectId, status?)` and `getIssue(issueId)` following the sessions API pattern
- Created `mobile/src/components/IssueStatusBadge.tsx` with colored dots: open (#2196F3 blue), in_progress (#FFC107 yellow), closed (#4CAF50 green)
- Created `mobile/src/components/IssueCard.tsx` with pressable card showing title, IssueStatusBadge, and relative timestamp
- Created `mobile/src/screens/ProjectIssuesScreen.tsx` following ProjectSessionsScreen pattern exactly: FlatList, pull-to-refresh, loading spinner, empty state ("No issues yet"), header title set to project name
- Added `ProjectIssues` route to `DashboardStackParamList` in `navigation/types.ts`
- Registered `ProjectIssuesScreen` in `DashboardStackNavigator` in `RootNavigator.tsx`
- Added "Issues" header button on `ProjectSessionsScreen` that navigates to `ProjectIssuesScreen` for the same project
- Files created: `mobile/src/api/issues.ts`, `mobile/src/components/IssueStatusBadge.tsx`, `mobile/src/components/IssueCard.tsx`, `mobile/src/screens/ProjectIssuesScreen.tsx`
- Files modified: `mobile/src/navigation/types.ts`, `mobile/src/navigation/RootNavigator.tsx`, `mobile/src/screens/ProjectSessionsScreen.tsx`
- Tests added: 12 new tests across 5 test files (`issue-status-badge.test.tsx`, `issue-card.test.tsx`, `project-issues-screen.test.tsx`, `issues-api.test.ts`, `issues-navigation.test.tsx`)
- Build results: 114 tests pass (31 suites), 0 fail, TypeScript clean (`npx tsc --noEmit` passes)
- Known limitations: IssueCard onPress is a no-op (issue detail screen is out of scope per issue spec)

### [QA] 2026-03-16 12:30
- Tests: 114 passed, 0 failed (13 new tests across 5 test files)
- TypeScript: clean (npx tsc --noEmit passes)
- Acceptance criteria:
  - listIssues(projectId) calls GET /api/projects/{projectId}/issues: PASS
  - getIssue(issueId) calls GET /api/issues/{issueId}: PASS
  - IssueStatusBadge renders blue/yellow/green dots for open/in_progress/closed: PASS
  - IssueCard displays title, IssueStatusBadge, and human-readable timestamp: PASS
  - IssueCard is pressable (accepts and calls onPress): PASS
  - ProjectIssuesScreen calls listIssues on mount and renders FlatList: PASS
  - ProjectIssuesScreen shows loading spinner during initial fetch: PASS
  - ProjectIssuesScreen supports pull-to-refresh via RefreshControl: PASS
  - ProjectIssuesScreen shows "No issues yet" empty state: PASS
  - ProjectIssuesScreen sets header title to project name: PASS
  - DashboardStackParamList includes ProjectIssues route with correct params: PASS
  - ProjectIssuesScreen registered in Dashboard stack navigator: PASS
  - Navigation from ProjectSessionsScreen to ProjectIssuesScreen via header button: PASS
  - No TypeScript errors: PASS
  - 13 new tests (exceeds 8+ requirement): PASS
- VERDICT: PASS

### [PM] 2026-03-16 13:00
- Reviewed diff: 4 new files (api/issues.ts, IssueStatusBadge.tsx, IssueCard.tsx, ProjectIssuesScreen.tsx), 3 modified files (types.ts, RootNavigator.tsx, ProjectSessionsScreen.tsx), 5 new test files
- Results verified: real data present -- 114 tests pass, TypeScript clean, 13 new tests cover all specified scenarios
- Code quality: clean implementation following existing patterns (ProjectSessionsScreen, SessionCard). API client matches sessions pattern. IssueStatusBadge uses correct hex colors. IssueCard has proper relative time formatting. Screen has loading/empty/list states with pull-to-refresh. Navigation wired via header button with testID.
- Acceptance criteria: all 15/15 met
  - [x] listIssues exports and calls correct endpoint
  - [x] getIssue exports and calls correct endpoint
  - [x] IssueStatusBadge renders correct colored dots (blue/yellow/green)
  - [x] IssueCard displays title, badge, and timestamp
  - [x] IssueCard is pressable with onPress callback
  - [x] ProjectIssuesScreen calls listIssues on mount, renders FlatList
  - [x] Loading spinner during initial fetch
  - [x] Pull-to-refresh via RefreshControl
  - [x] "No issues yet" empty state
  - [x] Header title set to project name
  - [x] DashboardStackParamList includes ProjectIssues route
  - [x] ProjectIssuesScreen registered in Dashboard stack navigator
  - [x] Navigation from ProjectSessionsScreen via header button
  - [x] No TypeScript errors
  - [x] 13 new tests (exceeds 8+ requirement)
- Follow-up issues created: none needed (issue detail screen was explicitly out of scope per spec)
- VERDICT: ACCEPT
