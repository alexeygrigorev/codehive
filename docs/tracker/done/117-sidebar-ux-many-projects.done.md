# Issue #117: Sidebar redesign -- flat project list with search and time grouping

## Problem

The current sidebar lists all projects in a flat list with expand/collapse toggles for sessions. With many projects (10+), the sidebar becomes unwieldy -- it takes up too much vertical space, there is no way to find a specific project quickly, and there is no visual organization. This is a common UX problem that ChatGPT and Claude have both solved with a similar pattern.

## Design Reference: ChatGPT / Claude Sidebar Pattern

Both ChatGPT and Claude use a sidebar pattern that scales well to hundreds of items:

1. **Flat list of items** -- each item is a single line (project name), no nested sessions visible
2. **Grouped by recency** -- "Today", "Yesterday", "Previous 7 days", "Previous 30 days", "Older"
3. **Search/filter at the top** -- a search input that filters the list in real time as you type
4. **Collapsible groups** -- each time group can be collapsed
5. **Active item highlighted** -- the currently open item is visually distinct
6. **Clicking an item navigates directly** -- no expand/collapse for sub-items in the sidebar; sessions are shown on the project page itself
7. **New item button** at the top -- "New Project" button always visible

This is the target UX for the Codehive sidebar.

## Scope

Redesign `web/src/components/Sidebar.tsx` to follow the ChatGPT/Claude sidebar pattern. The sidebar becomes a flat, searchable, time-grouped list of projects. Session listing moves out of the sidebar entirely -- sessions are already shown on the project detail page.

### In Scope

- Flat project list (no nested session trees in sidebar)
- Search input at the top of the project list that filters by project name
- Time-based grouping: "Today", "Yesterday", "Previous 7 days", "Previous 30 days", "Older"
- Collapsible time groups (expanded by default)
- Active project highlighting
- Project count in header ("Projects (12)")
- "New Project" button in sidebar header
- Existing sidebar collapse-to-icons functionality preserved
- Independent scroll for the project list area
- Keyboard shortcut for search focus (Ctrl+K or /)

### Out of Scope

- Drag-and-drop reordering
- Pinned/favorited projects (future issue)
- Project deletion from sidebar
- Session listing in sidebar (removed -- sessions are on the project page)

## Dependencies

- None. This is a standalone UI redesign of an existing component.

## User Stories

### Story 1: Developer quickly finds a project using search

1. User opens the app at /
2. Sidebar is visible on the left showing projects grouped by time ("Today", "Previous 7 days", etc.)
3. User sees 15+ projects in the sidebar
4. User clicks the search input at the top of the sidebar (or presses Ctrl+K)
5. User types "myapp"
6. The project list filters in real time -- only projects containing "myapp" in their name are shown
7. Time group headers that have no matching projects are hidden
8. User clicks the matching project "myapp-backend"
9. User is navigated to /projects/{id}
10. The search input clears and the full list is restored

### Story 2: Developer browses projects organized by recency

1. User opens the app at /
2. Sidebar shows projects grouped under time headers:
   - "Today" -- projects created today
   - "Yesterday" -- projects created yesterday
   - "Previous 7 days" -- projects created in the last week
   - "Previous 30 days" -- projects created in the last month
   - "Older" -- everything else
3. Each group header shows the group name
4. The most recent projects appear at the top
5. User clicks a group header to collapse it
6. The group's projects are hidden, header shows a collapsed indicator
7. User clicks again to expand

### Story 3: Developer creates a new project from the sidebar

1. User sees a "New Project" button at the top of the sidebar (below the search input)
2. User clicks "New Project"
3. User is navigated to /projects/new

### Story 4: Active project is visually highlighted

1. User is on /projects/{id} for project "myapp"
2. In the sidebar, "myapp" is visually highlighted (different background, bold text)
3. The time group containing "myapp" is expanded
4. User navigates to a different project
5. The highlight moves to the new project

### Story 5: Sidebar collapse to icons still works

1. User clicks the collapse toggle button
2. Sidebar narrows to icon-only width (existing behavior)
3. Project names, search, and time groups are hidden
4. User clicks expand to restore full sidebar
5. Collapse state persists across page reloads (localStorage)

### Story 6: Empty state and project count

1. User has 12 projects
2. Sidebar header shows "Projects (12)"
3. If user has 0 projects, sidebar shows "No projects yet" message
4. The project count updates when the search filter is active -- shows filtered count (e.g., "Projects (3 of 12)")

## E2E Test Scenarios

### E2E 1: Search filters projects (maps to Story 1)

**Preconditions:** At least 3 projects exist with distinct names (e.g., "alpha-web", "beta-api", "gamma-cli")

**Steps:**
1. Navigate to /
2. Locate the sidebar search input
3. Type "alpha" into the search input
4. Assert: only "alpha-web" is visible in the sidebar project list
5. Assert: "beta-api" and "gamma-cli" are NOT visible
6. Clear the search input
7. Assert: all 3 projects are visible again

**Screenshots:** After step 4 (filtered state), after step 7 (restored state)

### E2E 2: Time grouping is displayed (maps to Story 2)

**Preconditions:** At least 2 projects exist -- one created today, one created more than 7 days ago

**Steps:**
1. Navigate to /
2. Assert: sidebar contains at least one time group header (e.g., text matching "Today" or "Previous 7 days" or "Older")
3. Assert: projects appear under their respective time group headers
4. Click a time group header to collapse it
5. Assert: projects in that group are hidden
6. Click the header again to expand
7. Assert: projects are visible again

**Screenshots:** After step 2 (groups visible), after step 4 (collapsed group)

### E2E 3: New Project button navigates correctly (maps to Story 3)

**Preconditions:** App is running

**Steps:**
1. Navigate to /
2. Locate the "New Project" button/link in the sidebar
3. Click it
4. Assert: URL is /projects/new
5. Assert: the new project page is displayed

**Screenshots:** After step 2 (button visible in sidebar)

### E2E 4: Active project highlighting (maps to Story 4)

**Preconditions:** At least 2 projects exist

**Steps:**
1. Navigate to /projects/{first-project-id}
2. Assert: the first project in the sidebar has the active/highlighted style (e.g., a specific CSS class or background color)
3. Navigate to /projects/{second-project-id}
4. Assert: the second project now has the active style
5. Assert: the first project no longer has the active style

**Screenshots:** After step 2, after step 4

### E2E 5: Sidebar collapse preserves functionality (maps to Story 5)

**Preconditions:** App is running with at least 1 project

**Steps:**
1. Navigate to /
2. Assert: sidebar is in expanded state (width > 100px, search input visible)
3. Click the sidebar collapse toggle
4. Assert: sidebar is in collapsed state (narrow width, search input NOT visible)
5. Reload the page
6. Assert: sidebar is still in collapsed state (persisted via localStorage)
7. Click the toggle to expand
8. Assert: sidebar is expanded again, search input visible

**Screenshots:** After step 2 (expanded), after step 4 (collapsed)

### E2E 6: Project count display (maps to Story 6)

**Preconditions:** At least 3 projects exist

**Steps:**
1. Navigate to /
2. Assert: sidebar header shows project count text matching pattern "Projects (N)" where N >= 3
3. Type a search query that matches only 1 project
4. Assert: sidebar header shows filtered count pattern like "Projects (1 of N)"

**Screenshots:** After step 2, after step 4

## Acceptance Criteria

- [ ] Sidebar shows a flat list of projects (no nested session trees)
- [ ] Search input at top of sidebar filters projects by name in real time
- [ ] Projects are grouped by time: "Today", "Yesterday", "Previous 7 days", "Previous 30 days", "Older"
- [ ] Time groups are collapsible (click header to toggle)
- [ ] Active project (matching current URL) is visually highlighted
- [ ] "New Project" button/link in sidebar navigates to /projects/new
- [ ] Header shows project count ("Projects (12)"), updates when filtering ("Projects (3 of 12)")
- [ ] Sidebar collapse-to-icons feature still works, state persisted in localStorage
- [ ] Project list area scrolls independently (overflow-y-auto)
- [ ] Search input is focusable via keyboard shortcut (Ctrl+K or /)
- [ ] Empty state message shown when no projects exist
- [ ] All 6 e2e test scenarios pass in Playwright
- [ ] Existing Sidebar unit tests updated to reflect new structure
- [ ] `cd web && npx vitest run` passes
- [ ] `cd web && npx tsc --noEmit` passes
- [ ] Dark theme styling maintained (existing bg-gray-900 palette)

## Technical Notes

- The current `Sidebar.tsx` already has collapse toggle, project listing, and session expand/collapse. The redesign replaces the session tree with time-grouped flat list + search.
- `ProjectRead` already has `created_at` field -- use this for time grouping.
- The `fetchProjects` API already returns all projects. Filtering and grouping happens client-side.
- Remove `fetchSessions` dependency from Sidebar -- sessions are shown on the project page, not in the sidebar.
- Preserve `data-testid="sidebar"` and `data-testid="sidebar-toggle"` for existing tests.
- Add new test IDs: `data-testid="sidebar-search"`, `data-testid="sidebar-project-count"`, `data-testid="sidebar-new-project"`, `data-testid="time-group-{name}"`.

## Related

- #116 -- e2e test isolation will reduce junk test projects, but this UX must handle many real projects gracefully regardless

## Log

### [SWE] 2026-03-18 23:55
- Rewrote `web/src/components/Sidebar.tsx` -- replaced session tree with flat project list, time grouping, search, collapsible groups, active highlighting
- Removed all session-related code from sidebar (fetchSessions import, session expand/collapse, session listing)
- Added search input with Ctrl+K keyboard shortcut
- Added time-based grouping: Today, Yesterday, Previous 7 days, Previous 30 days, Older
- Added collapsible time groups with expand/collapse toggles
- Added project count header with filtered count display ("Projects (3 of 12)")
- Added "New Project" button linking to /projects/new
- Added empty state message when no projects exist
- Preserved sidebar collapse-to-icons functionality with localStorage persistence
- Independent scroll for project list area (overflow-y-auto)
- Rewrote `web/src/test/Sidebar.test.tsx` -- 18 unit tests covering all new features
- Created `web/e2e/sidebar-ux.spec.ts` -- 6 e2e tests matching all PM scenarios
- Files modified: web/src/components/Sidebar.tsx, web/src/test/Sidebar.test.tsx
- Files created: web/e2e/sidebar-ux.spec.ts
- Tests added: 18 unit tests, 6 e2e tests
- Build results: 645 vitest tests pass, 0 fail; tsc --noEmit clean; 6/6 e2e tests pass
- Screenshots saved to /tmp/sidebar-e2e*.png (14 screenshots total)
- Known limitations: none

### [QA] 2026-03-19 00:10
- Unit tests: 645 passed, 0 failed (vitest run output clean)
- tsc --noEmit: clean, no errors
- E2E tests: 5 passed, 1 failed (E2E 2: time grouping)
  - E2E 1 (search filters): PASS
  - E2E 2 (time grouping): FAIL -- test expects `time-group-today` but projects created in beforeAll are classified as "Yesterday" when the clock crosses midnight UTC. The time grouping feature itself works correctly (screenshot evidence shows "YESTERDAY" group header and projects listed under it). The test has a flaky midnight-boundary assumption.
  - E2E 3 (New Project button): PASS
  - E2E 4 (active highlighting): PASS
  - E2E 5 (sidebar collapse): PASS
  - E2E 6 (project count): PASS
- Screenshots reviewed:
  - /tmp/sidebar-qa-1-full.png: sidebar shows flat project list, "PROJECTS (154)" header, search input, "+ New Project" button, "YESTERDAY" time group
  - /tmp/sidebar-qa-2-search.png: "PROJECTS (33 OF 154)" with "alpha" typed, only alpha-* projects visible
  - /tmp/sidebar-qa-4-collapsed.png: sidebar collapsed to narrow icon-only width, first-letter icons visible
  - /tmp/sidebar-e2e4-first-active.png: "alpha-web-mmwni2q2" highlighted with distinct background in sidebar
  - /tmp/sidebar-e2e6-filtered-count.png: "PROJECTS (1 OF 154)" with filtered search active
  - /tmp/sidebar-qa-6-active.png: "+ New Project" navigates to /projects/new page
- Acceptance criteria:
  1. Flat list of projects (no nested sessions): PASS
  2. Search input filters by name in real time: PASS
  3. Time groups (Today, Yesterday, Previous 7 days, Previous 30 days, Older): PASS
  4. Time groups collapsible: PASS (unit test passes, code verified)
  5. Active project highlighted: PASS (screenshot evidence)
  6. New Project button navigates to /projects/new: PASS
  7. Project count header with filtered count: PASS
  8. Sidebar collapse-to-icons with localStorage persistence: PASS
  9. Project list scrolls independently (overflow-y-auto): PASS (code verified)
  10. Search focusable via Ctrl+K or /: PASS (code verified)
  11. Empty state message: PASS (unit test passes)
  12. All 6 e2e tests pass: FAIL -- E2E 2 fails due to flaky midnight-boundary assumption in test
  13. Existing Sidebar unit tests updated: PASS (18 tests)
  14. vitest run passes: PASS (645 tests)
  15. tsc --noEmit passes: PASS
  16. Dark theme styling maintained: PASS (bg-gray-900 palette visible in screenshots)
- VERDICT: FAIL
- Issue: E2E 2 test (`time grouping is displayed`) fails because it hardcodes `time-group-today` in the assertion, but projects created in `beforeAll` are classified as "Yesterday" when the test runs after midnight UTC. The fix is to make the test resilient to time boundaries -- instead of asserting for "Today" specifically, assert that at least one time group header exists (e.g., check for any of the group test IDs). Alternatively, check for whichever group the newly-created projects actually fall into.

### [PM] 2026-03-19 00:11
- Reviewed diff: 3 files changed (Sidebar.tsx, Sidebar.test.tsx, sidebar-ux.spec.ts)
- Reviewed all 12 screenshots from SWE e2e runs:
  - e2e1: search filters correctly (full list -> filtered "1 OF 151" -> restored)
  - e2e2: time grouping works (TODAY header with projects, collapsed state hides projects)
  - e2e3: New Project button visible in sidebar
  - e2e4: active project highlighting moves correctly between projects (bg-gray-800 + font-medium)
  - e2e5: sidebar collapse to icon-only width (first-letter icons), expand restores full sidebar
  - e2e6: project count shows total (154) and filtered format (1 OF 154)
- Results verified: real screenshots with real data present, all matching expected UX
- Vitest: 645 tests pass, 0 failures (confirmed by running locally)
- E2E timezone fix verified: E2E 2 now uses dynamic group detection (`[data-testid^="time-group-"]`) instead of hardcoded "Today"
- Code review: clean implementation, follows ChatGPT/Claude sidebar pattern, no over-engineering
- Acceptance criteria: all 16 met
  1. Flat project list (no sessions): PASS
  2. Search filters in real time: PASS
  3. Time groups (Today/Yesterday/Previous 7 days/Previous 30 days/Older): PASS
  4. Collapsible time groups: PASS
  5. Active project highlighted: PASS
  6. New Project button -> /projects/new: PASS
  7. Project count with filtered display: PASS
  8. Sidebar collapse with localStorage persistence: PASS
  9. Independent scroll (overflow-y-auto): PASS
  10. Keyboard shortcut (Ctrl+K, /): PASS
  11. Empty state message: PASS
  12. All 6 e2e tests pass: PASS (timezone fix applied)
  13. Unit tests updated: PASS (18 tests)
  14. vitest run passes: PASS (645 tests)
  15. tsc --noEmit passes: PASS
  16. Dark theme maintained: PASS
- No scope dropped, no follow-up issues needed
- User perspective: sidebar now follows the ChatGPT/Claude pattern -- flat list, searchable, time-grouped, scales to 150+ projects. The user will be satisfied.
- VERDICT: ACCEPT
