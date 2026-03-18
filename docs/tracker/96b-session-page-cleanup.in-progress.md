# Issue #96b: Session page cleanup -- tool call log, collapsible sidebar, layout

## Problem

The session page has several UX issues:

1. **Raw timeline**: The Timeline tab in the right sidebar shows raw event types (e.g. `tool.call.started`, `file.changed`) with no human-readable descriptions. This is noise, not information.
2. **Non-collapsible sidebar**: The right sidebar (ToDo, Changed Files, Timeline, etc.) always takes 320px. On smaller screens or when focused on the chat, users cannot collapse it.
3. **Cluttered header bar**: Mode indicator, approval badge, status, and history search are all crammed into one row with no clear grouping.
4. **No back navigation**: There is no link back to the parent project from the session page (breadcrumb is handled by #96a, but the session header should also show the project name).

## Scope

Improve the session page layout and replace the raw timeline with a clean tool call log. Pure frontend work.

**In scope:**
1. Replace raw `TimelinePanel` with a human-readable `ToolCallLog` panel
2. Make the right sidebar collapsible (toggle button to hide/show)
3. Clean up the session header layout (group related elements)
4. Show project name in session header (link to project page)

**Out of scope:**
- Breadcrumb component (covered by #96a)
- Navigation sidebar changes (covered by #96a)
- Dark theme (covered by #89)
- New sidebar panel types (existing panels are sufficient)

## Dependencies

- None. All backend APIs already exist:
  - `GET /api/sessions/{id}/events` -- event list (already used by TimelinePanel)
  - `GET /api/sessions/{id}` -- session detail (already includes `project_id`)
  - `GET /api/projects/{id}` -- project detail (for project name)

## Requirements

### 1. Tool call log (replaces raw Timeline)

- Rename the "Timeline" tab to "Activity"
- Replace `TimelinePanel` content with a grouped, human-readable activity log
- Group events by type and show meaningful descriptions:
  - `tool.call.started` / `tool.call.finished` -- show tool name (from event `data.tool` or `data.name` field) and duration if both start/finish exist
  - `file.changed` -- show filename (from event `data.path` or `data.file` field)
  - `message.created` -- show "Message" with role
  - Other events -- show type in a readable format (replace dots with spaces, title case)
- Each entry shows: icon or colored dot by category, description, timestamp (HH:MM)
- Most recent events at the top
- Keep the existing `fetchEvents` API call -- just transform the display

### 2. Collapsible right sidebar

- Add a toggle button (vertical bar or chevron) on the left edge of the right sidebar
- Clicking it hides the sidebar panels, giving the full width to the chat panel
- When collapsed, show a thin vertical strip (~32px) with the toggle button
- When expanded, show the full 320px sidebar with tabs (existing `SidebarTabs`)
- Collapse state persists in localStorage (key: `session-sidebar-collapsed`)
- Smooth CSS transition on width change

### 3. Session header cleanup

- Reorganize the header bar into clear groups:
  - Left group: project name (link) + session name + status badge
  - Right group: mode indicator (clickable to toggle switcher) + approval badge
- Move `SessionHistorySearch` into the right sidebar as a tab or into the header as a small search icon toggle (either approach is acceptable)
- Remove visual clutter: reduce spacing, use consistent font sizes

### 4. Project context in header

- Fetch the parent project name using `project_id` from the session data
- Show it before the session name: "ProjectName / SessionName" or as a small link above the session name
- Clicking the project name navigates to `/projects/{project_id}`

## Acceptance Criteria

- [ ] Timeline tab is renamed to "Activity" in `SidebarTabs`
- [ ] Activity panel shows human-readable descriptions instead of raw event type strings
- [ ] Tool calls show the tool name (not just `tool.call.started`)
- [ ] File change events show the filename
- [ ] Right sidebar has a collapse/expand toggle button
- [ ] When collapsed, the chat panel takes full width; a thin strip with the toggle remains visible
- [ ] Sidebar collapse state persists in localStorage
- [ ] Session header shows the parent project name as a clickable link
- [ ] Session header groups elements cleanly: name/status on left, mode/approval on right
- [ ] `SessionHistorySearch` is moved out of the main content flow (into sidebar tab or header icon)
- [ ] `cd web && npx vitest run` passes with tests for the new activity panel and collapsible sidebar
- [ ] No TypeScript errors: `cd web && npx tsc --noEmit` passes
- [ ] Existing session page tests still pass

## Test Scenarios

### Unit: Activity panel (ToolCallLog)
- Renders tool call events with tool name extracted from event data
- Renders file change events with filename extracted from event data
- Renders message events with role
- Falls back to formatted event type for unknown event types
- Shows timestamps in HH:MM format
- Shows "No activity yet" when events array is empty

### Unit: Collapsible sidebar
- Sidebar renders expanded by default (or per localStorage)
- Clicking toggle button collapses the sidebar
- Clicking toggle button again expands the sidebar
- Collapsed state is saved to localStorage
- Chat panel takes full width when sidebar is collapsed

### Unit: Session header
- Shows project name as a link to `/projects/{id}`
- Shows session name and status badge
- Shows mode indicator and approval badge on the right
- Clicking project name navigates correctly

### Integration: Session page layout
- Page loads session and project data
- Activity tab shows formatted events (not raw types)
- Collapsing sidebar gives chat full width
- All existing sidebar tabs (ToDo, Changed Files, Sub-agents, etc.) still work

## Notes

- The `EventRead` type has: `id`, `type`, `data` (object), `created_at`
- The `data` field structure varies by event type -- inspect actual event data to determine the correct field names for tool name, file path, etc.
- The existing `TimelinePanel` component can be refactored in place or replaced with a new component
- Keep the same tab structure in `SidebarTabs` -- just rename "Timeline" to "Activity" and swap the panel component
- This is a single-user self-hosted tool -- no multi-user concerns

## Log

### [SWE] 2026-03-18 10:35
- Created `ActivityPanel` component replacing raw `TimelinePanel` in sidebar
  - Groups events by type: tool calls show tool name, file changes show filename, messages show role
  - Falls back to formatted event type (dots/underscores to title case) for unknown types
  - Color-coded dots by category (blue=tool, green=file, purple=message, gray=other)
  - Most recent events displayed first
  - Exports `buildActivityEntry` and `formatEventType` for unit testing
- Updated `SidebarTabs`: renamed "Timeline" tab to "Activity", added "Search" tab
  - Swapped `TimelinePanel` for `ActivityPanel`
  - Added `SessionHistorySearch` as a sidebar tab instead of main content flow
- Updated `SessionPage` with collapsible right sidebar
  - Toggle button (chevron) on left edge of sidebar
  - Collapsed state: 32px thin strip; expanded: 320px full sidebar
  - Collapse state persists in localStorage (key: `session-sidebar-collapsed`)
  - CSS transition on width change
- Cleaned up session header layout
  - Left group: project name link + "/" + session name + status badge
  - Right group: mode indicator button + approval badge
  - Removed `SessionHistorySearch` from main content flow (moved to sidebar Search tab)
  - Project name shown as clickable link to `/projects/{id}`
- Files created: `web/src/components/sidebar/ActivityPanel.tsx`, `web/src/test/ActivityPanel.test.tsx`, `web/src/test/SessionSidebar.test.tsx`
- Files modified: `web/src/components/sidebar/SidebarTabs.tsx`, `web/src/pages/SessionPage.tsx`, `web/src/test/SidebarTabs.test.tsx`, `web/src/test/SessionPage.test.tsx`, `web/src/test/SessionPageModeApprovals.test.tsx`
- Tests added: 25 new tests (14 ActivityPanel, 4 buildActivityEntry/formatEventType, 7 collapsible sidebar)
- Build results: 546 tests pass, 0 fail, tsc --noEmit clean
- TimelinePanel component retained in codebase (not deleted) for backward compatibility; simply no longer referenced by SidebarTabs

### [QA] 2026-03-18 12:15
- Tests: 567 passed, 0 failed (all tests including 25 new ActivityPanel + SessionSidebar tests)
- TypeScript: `tsc -b` clean
- ESLint: fixed 2 `react-refresh/only-export-components` errors in ActivityPanel.tsx by extracting `buildActivityEntry` and `formatEventType` to a separate `activityUtils.ts` file. After fix: clean.
- Acceptance criteria:
  - Timeline tab is renamed to "Activity" in SidebarTabs: PASS
  - Activity panel shows human-readable descriptions instead of raw event type strings: PASS
  - Tool calls show the tool name (not just `tool.call.started`): PASS
  - File change events show the filename: PASS
  - Right sidebar has a collapse/expand toggle button: PASS
  - When collapsed, the chat panel takes full width; a thin strip with the toggle remains visible: PASS
  - Sidebar collapse state persists in localStorage: PASS
  - Session header shows the parent project name as a clickable link: PASS
  - Session header groups elements cleanly: name/status on left, mode/approval on right: PASS
  - SessionHistorySearch is moved out of the main content flow (into sidebar tab): PASS
  - `cd web && npx vitest run` passes with tests for the new activity panel and collapsible sidebar: PASS
  - No TypeScript errors: `cd web && npx tsc --noEmit` passes: PASS
  - Existing session page tests still pass: PASS
- Fix applied: Extracted `buildActivityEntry` and `formatEventType` from `ActivityPanel.tsx` into `activityUtils.ts` to resolve react-refresh lint rule. Updated test imports accordingly.
- VERDICT: PASS
