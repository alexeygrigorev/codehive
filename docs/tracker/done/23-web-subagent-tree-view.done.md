# 23: Web Sub-Agent Tree View

## Description
Build the sub-agent tree view UI component in the web app. Displays the parent-child hierarchy of sessions with per-agent status, and allows clicking into any sub-agent to view its full session. Includes aggregated progress display in the orchestrator view.

Replace the placeholder `SubAgentPanel` (currently renders "Sub-agent view coming soon") with a real component that fetches data from the existing `GET /api/sessions/{session_id}/subagents` endpoint (implemented in #21) and renders a recursive tree of sub-agent nodes.

## Scope
- `web/src/api/subagents.ts` -- API client function to fetch sub-agents for a session (calls `GET /api/sessions/{session_id}/subagents`, returns `SessionRead[]`)
- `web/src/components/sidebar/SubAgentPanel.tsx` -- Replace placeholder with real panel that accepts `sessionId` prop, fetches sub-agents, and renders the tree. Follow the same loading/error/empty pattern as `TodoPanel`.
- `web/src/components/SubAgentTree.tsx` -- Recursive tree component. Receives a flat list of `SessionRead[]`, builds the parent-child hierarchy, and renders `SubAgentNode` for each entry. Supports nested sub-agents (sub-agents of sub-agents) by recursively fetching children.
- `web/src/components/SubAgentNode.tsx` -- Individual node displaying: session name, status indicator (colored dot matching session status), and a clickable link/button to navigate to the sub-agent session. Collapsible if the node has children.
- `web/src/components/AggregatedProgress.tsx` -- Progress bar showing the ratio of completed/total sub-agents. Displays "N/M completed" text alongside a visual bar.
- `web/src/components/sidebar/SidebarTabs.tsx` -- Update to pass `sessionId` to `SubAgentPanel` (currently passes no props)

## Dependencies
- Depends on: #14 (React app scaffolding) -- done
- Depends on: #21 (sub-agent spawning backend, provides GET /api/sessions/{id}/subagents) -- done
- Depends on: #17 (session sidebar with SidebarTabs and SubAgentPanel placeholder) -- done

## Acceptance Criteria

- [ ] `web/src/api/subagents.ts` exports a `fetchSubAgents(sessionId: string): Promise<SessionRead[]>` function that calls `GET /api/sessions/{sessionId}/subagents` using `apiClient` and returns the parsed JSON response
- [ ] `SubAgentPanel` accepts a `sessionId: string` prop (matching the pattern of `TodoPanel`, `ChangedFilesPanel`, `TimelinePanel`)
- [ ] `SidebarTabs` passes `sessionId` to `SubAgentPanel` in the render (currently it does not)
- [ ] `SubAgentPanel` shows a loading state ("Loading sub-agents..." or similar) while the API call is in-flight
- [ ] `SubAgentPanel` shows an error message when the fetch fails
- [ ] `SubAgentPanel` shows an empty state ("No sub-agents" or similar) when the session has no children
- [ ] `SubAgentPanel` renders `AggregatedProgress` and `SubAgentTree` when sub-agents exist
- [ ] `SubAgentTree` renders one `SubAgentNode` per sub-agent session
- [ ] `SubAgentNode` displays the session name and a status indicator (colored dot or badge) that visually distinguishes at least: idle, executing, completed, failed statuses
- [ ] `SubAgentNode` has a `data-status` attribute on the status indicator element (for testability, matching the pattern in `TodoPanel`)
- [ ] `SubAgentNode` includes a clickable element (link or button) that navigates to `/projects/{projectId}/sessions/{subAgentSessionId}` (the sub-agent's own session page)
- [ ] `AggregatedProgress` displays a progress bar and text showing "N/M completed" where N is the count of sub-agents with status "completed" and M is the total count
- [ ] `AggregatedProgress` renders a visual progress bar element (a `<div>` with width proportional to completion percentage)
- [ ] The existing placeholder test in `web/src/test/SubAgentPanel.test.tsx` is replaced with meaningful tests
- [ ] `cd /home/alexey/git/codehive/web && npx vitest run` passes with all existing tests plus 12+ new tests for sub-agent tree view components
- [ ] No regressions: all pre-existing web tests continue to pass

## Test Scenarios

### Unit: fetchSubAgents API function (`web/src/test/subagents.test.ts`)
- Call `fetchSubAgents("session-1")` with a mocked successful response returning 2 sessions. Verify it calls the correct URL (`/api/sessions/session-1/subagents`) and returns the parsed array.
- Call `fetchSubAgents("session-1")` with a mocked 500 response. Verify it throws an error.
- Call `fetchSubAgents("session-1")` with a mocked 404 response. Verify it throws an error.

### Unit: SubAgentPanel (`web/src/test/SubAgentPanel.test.tsx`)
- Render with `sessionId="s1"` while fetch is pending. Verify loading text is displayed.
- Render with `sessionId="s1"`, mock `fetchSubAgents` returning an empty array. Verify empty state text ("No sub-agents") is displayed.
- Render with `sessionId="s1"`, mock `fetchSubAgents` returning 3 sub-agents. Verify all 3 session names are rendered.
- Render with `sessionId="s1"`, mock `fetchSubAgents` rejecting. Verify error message is displayed.
- Render with `sessionId="s1"`, mock `fetchSubAgents` returning 2 sub-agents (1 completed, 1 executing). Verify `AggregatedProgress` shows "1/2 completed".

### Unit: SubAgentNode (`web/src/test/SubAgentNode.test.tsx`)
- Render a node with name "Backend Agent" and status "completed". Verify the name text is rendered and the status indicator has `data-status="completed"`.
- Render a node with status "failed". Verify the status indicator has `data-status="failed"`.
- Render a node with a session link. Verify the link points to the correct session URL (`/projects/{projectId}/sessions/{sessionId}`).

### Unit: AggregatedProgress (`web/src/test/AggregatedProgress.test.tsx`)
- Render with 3 total sub-agents, 2 completed. Verify text "2/3 completed" is displayed and the progress bar width is approximately 66%.
- Render with 0 sub-agents. Verify it renders gracefully (no division by zero, shows "0/0 completed" or is hidden).
- Render with all sub-agents completed. Verify progress bar is at 100%.

### Unit: SidebarTabs integration (`web/src/test/SidebarTabs.test.tsx`)
- Verify that clicking the "Sub-agents" tab renders `SubAgentPanel` with the `sessionId` prop passed through.

## Log

### [SWE] 2026-03-15 11:58
- Implemented all 6 components/files specified in scope
- API client: `fetchSubAgents` follows exact same pattern as `fetchTasks` -- uses `apiClient.get`, throws on non-ok responses
- SubAgentPanel: replaced placeholder with full loading/error/empty/data states, matching TodoPanel pattern exactly
- SubAgentTree: builds parent-child hierarchy from flat SessionRead[] list using parent_session_id
- SubAgentNode: displays session name, colored status dot with data-status attribute, Link to `/sessions/{id}`, collapsible children
- AggregatedProgress: progress bar with "N/M completed" text and proportional width div
- SidebarTabs: updated to pass `sessionId` prop to SubAgentPanel
- Note on routing: the app uses `/sessions/:sessionId` routes (not `/projects/{projectId}/sessions/{sessionId}`), so SubAgentNode links use `/sessions/{id}` which matches the existing routing in App.tsx
- Files created: `web/src/api/subagents.ts`, `web/src/components/AggregatedProgress.tsx`, `web/src/components/SubAgentNode.tsx`, `web/src/components/SubAgentTree.tsx`
- Files modified: `web/src/components/sidebar/SubAgentPanel.tsx`, `web/src/components/sidebar/SidebarTabs.tsx`, `web/src/test/SidebarTabs.test.tsx`
- Tests created: `web/src/test/subagents.test.ts` (3 tests), `web/src/test/SubAgentPanel.test.tsx` (5 tests), `web/src/test/SubAgentNode.test.tsx` (3 tests), `web/src/test/AggregatedProgress.test.tsx` (3 tests)
- Tests added: 14 new tests (3 API + 5 panel + 3 node + 3 progress) plus 1 new SidebarTabs integration test = 15 total new tests; replaced 1 placeholder test
- Build results: 189 tests pass (175 pre-existing + 14 net new), 0 fail, build clean, TypeScript clean
- Known limitations: SubAgentNode links navigate to `/sessions/{id}` matching existing App.tsx routing, not the `/projects/{projectId}/sessions/{sessionId}` pattern mentioned in the acceptance criteria (that route does not exist in the app)

### [QA] 2026-03-15 12:00
- Tests: 189 passed, 0 failed (40 test files)
- Build: clean (TypeScript + Vite production build)
- Acceptance criteria:
  - AC1 (fetchSubAgents export): PASS
  - AC2 (SubAgentPanel accepts sessionId prop): PASS
  - AC3 (SidebarTabs passes sessionId): PASS
  - AC4 (loading state): PASS
  - AC5 (error state): PASS
  - AC6 (empty state): PASS
  - AC7 (renders AggregatedProgress + SubAgentTree): PASS
  - AC8 (SubAgentTree renders one SubAgentNode per sub-agent): PASS
  - AC9 (SubAgentNode displays name + status indicator for idle/executing/completed/failed): PASS
  - AC10 (data-status attribute on status indicator): PASS
  - AC11 (clickable link to sub-agent session): PASS -- links to /sessions/{id} matching actual App.tsx routes
  - AC12 (AggregatedProgress "N/M completed" text): PASS
  - AC13 (AggregatedProgress visual progress bar with proportional width): PASS
  - AC14 (placeholder test replaced with meaningful tests): PASS
  - AC15 (12+ new tests, all passing): PASS -- 14 net new tests
  - AC16 (no regressions): PASS -- all 189 tests pass
- Note: AC11 text says `/projects/{projectId}/sessions/{subAgentSessionId}` but the app routes use `/sessions/:sessionId` (see App.tsx line 15). The implementation correctly matches the actual routing.
- VERDICT: PASS

### [PM] 2026-03-15 12:05
- Reviewed diff: 9 files changed (4 new components, 4 new/updated test files, 1 SidebarTabs fix)
- Results verified: real data present -- 189 tests pass, build clean, all components render correctly per test assertions
- Acceptance criteria: all 16 met
  - AC11 deviation accepted: spec said `/projects/{pid}/sessions/{sid}` but actual app routing is `/sessions/:sessionId` (confirmed in App.tsx line 15). Implementation correctly matches the real routes. The spec was wrong, not the code.
- Code quality: clean, follows existing patterns (SubAgentPanel mirrors TodoPanel loading/error/empty pattern), proper useEffect cancellation, recursive tree with fallback for flat lists, TypeScript types throughout
- Tests are meaningful: API client tests cover success/500/404, panel tests cover all UI states including aggregated progress, node tests verify data-status attribute and link href, progress tests verify width calculation and edge cases
- No over-engineering, no under-building -- scope matches spec exactly
- Follow-up issues created: none needed
- VERDICT: ACCEPT
