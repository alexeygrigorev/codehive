# 78: Wire TunnelPanel into Web Sidebar

## Description

The `TunnelPanel` component (`web/src/components/TunnelPanel.tsx`) is fully built -- it lists tunnels, creates new ones, closes them, and shows preview links. However, it is not reachable from anywhere in the app. This issue wires it in via two paths:

1. **Dedicated `/tunnels` page** -- A new `TunnelsPage` that renders `TunnelPanel`, accessible from the main left-hand nav in `MainLayout`.
2. **Session sidebar tab** -- Add "Tunnels" as a 7th tab in `SidebarTabs`, so users can manage tunnels while working in a session.

The sidebar tab and the standalone page both render the same `TunnelPanel` component.

## Scope

### In scope
- Create `web/src/pages/TunnelsPage.tsx` that wraps `TunnelPanel` with a page heading.
- Add a `/tunnels` route in `App.tsx` inside the protected layout.
- Add a "Tunnels" nav link in `MainLayout` sidebar nav (alongside "Dashboard").
- Add `"tunnels"` to the `TabKey` union and `TABS` array in `SidebarTabs.tsx`.
- Render `TunnelPanel` when the tunnels tab is selected in the sidebar.
- Update existing `SidebarTabs` tests to account for 7 tabs.
- Add tests for the new page and routing.

### Out of scope
- Changes to `TunnelPanel` internals or the tunnel API layer.
- Mobile-specific layout changes for tunnels (can be a follow-up).
- WebSocket-based live tunnel status updates.

## Dependencies

- Depends on: #41 (tunnel manager) -- DONE
- Depends on: #17 (web sidebar) -- DONE

## Acceptance Criteria

- [ ] A `/tunnels` route exists and is protected (requires auth).
- [ ] Navigating to `/tunnels` renders the `TunnelPanel` component inside a page wrapper with a heading.
- [ ] `MainLayout` nav sidebar contains a "Tunnels" link that navigates to `/tunnels` and highlights when active.
- [ ] `SidebarTabs` renders 7 tabs: ToDo, Changed Files, Timeline, Sub-agents, Questions, Checkpoints, Tunnels.
- [ ] Clicking the "Tunnels" sidebar tab displays `TunnelPanel` and hides the previously active panel.
- [ ] The `TabKey` type includes `"tunnels"`.
- [ ] `uv run npm --prefix web test -- --run` passes all tests, including new ones (12+ total in `SidebarTabs.test.tsx`).
- [ ] No existing tests are broken.

## Test Scenarios

### Unit: SidebarTabs with Tunnels tab
- Verify `SidebarTabs` renders all 7 tab labels including "Tunnels".
- Click the "Tunnels" tab, verify `TunnelPanel` is rendered and the previously visible panel is removed.
- Verify `onTabChange` callback fires with `"tunnels"` when the Tunnels tab is clicked.
- Verify the active CSS class applies correctly to the Tunnels tab.

### Unit: TunnelsPage
- Render `TunnelsPage`, verify it contains a heading (e.g. "Tunnels") and the `TunnelPanel` component.

### Integration: Routing
- Render the app with an authenticated user, navigate to `/tunnels`, verify `TunnelsPage` is displayed.
- Verify `/tunnels` is not accessible without authentication (redirects to login).

### Integration: MainLayout nav
- Render `MainLayout`, verify a "Tunnels" nav link is present.
- Verify the link points to `/tunnels`.

## Log

### [SWE] 2026-03-16 16:25
- Implemented all acceptance criteria for wiring TunnelPanel into the web app
- Added "tunnels" to TabKey union and TABS array in SidebarTabs.tsx, rendering TunnelPanel when selected
- Created TunnelsPage.tsx with heading and TunnelPanel
- Added /tunnels route in App.tsx inside the protected layout
- Added "Tunnels" NavLink in MainLayout sidebar nav alongside Dashboard
- Updated SidebarTabs.test.tsx: changed "six tabs" test to "seven tabs", added 3 new Tunnels-specific tests (render panel, onTabChange callback, active CSS class)
- Created TunnelsPage.test.tsx with 2 tests (heading, TunnelPanel render)
- Updated App.test.tsx: added /tunnels route to test router, added TunnelsPage rendering test, added Tunnels nav link test
- Files modified: web/src/components/sidebar/SidebarTabs.tsx, web/src/layouts/MainLayout.tsx, web/src/App.tsx
- Files created: web/src/pages/TunnelsPage.tsx, web/src/test/TunnelsPage.test.tsx
- Files updated (tests): web/src/test/SidebarTabs.test.tsx, web/src/test/App.test.tsx
- Build results: 459 tests pass, 0 fail, build clean
- SidebarTabs.test.tsx now has 13 tests (was 10, added 3)
- Known limitations: none

### [QA] 2026-03-16 16:30
- Tests: 459 passed, 0 failed (npx vitest run)
- Acceptance criteria:
  1. `/tunnels` route exists and is protected (inside ProtectedRoute): PASS
  2. `/tunnels` renders TunnelPanel inside page wrapper with heading: PASS
  3. MainLayout nav sidebar contains "Tunnels" link to `/tunnels` with active highlight: PASS
  4. SidebarTabs renders 7 tabs (ToDo, Changed Files, Timeline, Sub-agents, Questions, Checkpoints, Tunnels): PASS
  5. Clicking "Tunnels" sidebar tab displays TunnelPanel and hides previous panel: PASS
  6. TabKey type includes "tunnels": PASS
  7. All tests pass, 13 tests in SidebarTabs.test.tsx (12+ required): PASS
  8. No existing tests broken: PASS
- VERDICT: PASS

### [PM] 2026-03-16 16:45
- Reviewed diff: 7 web files changed (3 modified, 2 created, 2 test files updated), plus unrelated telegram changes in same working tree
- Results verified: 459 tests pass, 0 failures; 7 new tests covering all acceptance criteria
- Acceptance criteria: all 8 met
  1. /tunnels route inside ProtectedRoute in App.tsx: PASS
  2. TunnelsPage renders heading + TunnelPanel: PASS
  3. MainLayout NavLink to /tunnels with active highlight: PASS
  4. SidebarTabs renders 7 tabs including Tunnels: PASS
  5. Clicking Tunnels tab shows TunnelPanel, hides previous: PASS
  6. TabKey union includes "tunnels": PASS
  7. 13 tests in SidebarTabs.test.tsx (12+ required): PASS
  8. No existing tests broken: PASS
- Code quality: clean, follows existing patterns (same tab wiring as other 6 tabs), no over-engineering
- Follow-up issues created: none needed
- VERDICT: ACCEPT
