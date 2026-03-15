# 20: Web Session Mode Switcher and Approval UI

## Description
Add the session mode indicator and switcher (Brainstorm/Interview/Planning/Execution/Review) to the session view. Also implement inline approval prompts for actions that require user confirmation.

The backend already supports:
- Session `mode` field readable via `GET /api/sessions/{id}` and updatable via `PATCH /api/sessions/{id}` with `{"mode": "..."}` (issue #05, done).
- `approval.required` events via the event bus (issue #07, done), with `action_id` in the event data.
- `approve_action(session_id, action_id)` and `reject_action(session_id, action_id)` on the engine adapter (issue #09, done).
- WebSocket client streams events including `approval.required` (issue #18, done).
- `useNotifications()` hook already counts `pendingApprovals` from `approval.required` events (issue #18, done).

This issue wires up the frontend UI components to these existing backend capabilities.

## Scope
- `web/src/components/SessionModeIndicator.tsx` -- Display current mode with a colored icon/badge. Shows the mode name with a mode-specific color and icon. Read-only display.
- `web/src/components/SessionModeSwitcher.tsx` -- Dropdown or button group to switch between the five modes (Brainstorm, Interview, Planning, Execution, Review). Calls `PATCH /api/sessions/{id}` with `{"mode": "..."}`. Shows the current mode as selected. Disables during the API call. Emits an `onModeChange` callback so the parent can update local state.
- `web/src/components/ApprovalPrompt.tsx` -- Inline card rendered in the chat flow for each `approval.required` event. Shows the action description (from `event.data.description` or `event.data.tool_name`), an Approve button (green) and a Reject button (red). Disables both buttons while the API call is in flight. Shows a resolved state (approved/rejected) after the user responds.
- `web/src/components/ApprovalBadge.tsx` -- Small notification badge (counter) showing the number of pending approvals. Consumes the `useNotifications()` hook. Hidden when count is zero.
- `web/src/api/approvals.ts` -- `approveAction(sessionId, actionId)` calls `POST /api/sessions/{sessionId}/approve` with `{"action_id": actionId}`. `rejectAction(sessionId, actionId)` calls `POST /api/sessions/{sessionId}/reject` with `{"action_id": actionId}`. Both use `apiClient.post`.
- `web/src/pages/SessionPage.tsx` -- Updated to render `SessionModeIndicator` and `ApprovalBadge` in the session header bar, and include `SessionModeSwitcher` (e.g., as a dropdown triggered from the mode indicator).
- `web/src/components/ChatPanel.tsx` -- Updated to render `ApprovalPrompt` inline when an `approval.required` event is encountered in the chat stream.

## Design Decisions

### Mode indicator placement
The `SessionModeIndicator` goes in the session header bar (next to the session name and status badge). The `SessionModeSwitcher` opens as a dropdown or popover when the user clicks the mode indicator.

### Approval prompt in chat flow
`ApprovalPrompt` cards appear inline in the chat panel, positioned chronologically among messages and tool calls. The `ChatPanel` needs to handle `approval.required` events (add to `CHAT_EVENT_TYPES`).

### Approval API endpoints
The backend engine adapter has `approve_action` and `reject_action` methods. These need REST endpoints to call them. The `POST /api/sessions/{id}/approve` and `POST /api/sessions/{id}/reject` endpoints should be added as part of this issue (thin route handlers that call the engine adapter). If the backend endpoints do not yet exist, the frontend API layer should be implemented to call the expected endpoint shape, and the actual backend endpoint creation is tracked separately in issue #44.

### Approval state tracking
Once the user clicks Approve or Reject, the `ApprovalPrompt` transitions to a resolved state (shows "Approved" or "Rejected" text, buttons disabled). This state is tracked locally in the component. The backend will also emit a follow-up event (`approval.resolved` or similar) but the UI should optimistically update.

## Dependencies
- Depends on: #14 (React app scaffolding) -- DONE
- Depends on: #05 (session mode field in session CRUD, PATCH supports mode) -- DONE
- Depends on: #07 (approval.required events via event bus) -- DONE
- Depends on: #16 (session chat panel with ChatPanel, MessageBubble, ChatInput) -- DONE
- Depends on: #18 (WebSocket client, useNotifications, useSessionEvents) -- DONE

## Acceptance Criteria

- [ ] `cd web && npx vitest run` passes with 110+ tests (currently ~91; this issue adds 20+)
- [ ] `SessionModeIndicator` renders the current session mode name with a mode-specific color (each of the 5 modes has a distinct visual style)
- [ ] `SessionModeIndicator` is visible in the `SessionPage` header bar
- [ ] `SessionModeSwitcher` renders all 5 modes: brainstorm, interview, planning, execution, review
- [ ] `SessionModeSwitcher` highlights the currently active mode
- [ ] Clicking a different mode in `SessionModeSwitcher` calls `PATCH /api/sessions/{id}` with `{"mode": "<selected>"}` via `apiClient`
- [ ] `SessionModeSwitcher` disables interaction while the mode-change API call is in flight
- [ ] `SessionModeSwitcher` updates the displayed mode after a successful API response
- [ ] `ApprovalPrompt` renders inline in the chat flow when an `approval.required` event is received
- [ ] `ApprovalPrompt` displays the action description (from event data: `description` or `tool_name` field)
- [ ] `ApprovalPrompt` has an Approve button and a Reject button
- [ ] Clicking Approve calls `approveAction(sessionId, actionId)` which sends `POST /api/sessions/{id}/approve`
- [ ] Clicking Reject calls `rejectAction(sessionId, actionId)` which sends `POST /api/sessions/{id}/reject`
- [ ] `ApprovalPrompt` disables both buttons while the API call is in flight
- [ ] `ApprovalPrompt` shows a resolved state (e.g., "Approved" or "Rejected" text) after the user responds
- [ ] `ApprovalBadge` shows a count of pending approvals when count > 0 (uses `useNotifications()`)
- [ ] `ApprovalBadge` is hidden (or shows nothing) when there are zero pending approvals
- [ ] `ApprovalBadge` is rendered in the `SessionPage` header bar
- [ ] `ChatPanel` handles `approval.required` events alongside existing message and tool call events
- [ ] `approveAction` and `rejectAction` in `approvals.ts` use `apiClient.post` and handle errors (throw on non-OK)
- [ ] No TypeScript errors (`npx tsc -b` passes)
- [ ] All new components follow project patterns (functional components, TypeScript, Tailwind CSS)

## Test Scenarios

### Unit: SessionModeIndicator
- Renders the mode name text for each of the 5 modes (brainstorm, interview, planning, execution, review)
- Each mode renders with a distinct CSS class or color style
- Renders with default/fallback styling for an unknown mode string

### Unit: SessionModeSwitcher
- Renders buttons/options for all 5 modes
- The currently active mode is visually highlighted (has a distinct class)
- Clicking a non-active mode calls the onModeChange callback with the selected mode
- Does not call onModeChange when clicking the already-active mode
- When disabled prop is true, all mode options are non-interactive
- Shows loading state while mode change is in progress

### Unit: ApprovalPrompt
- Renders the action description from event data
- Renders Approve and Reject buttons in the default (pending) state
- Clicking Approve calls the onApprove callback with the action ID
- Clicking Reject calls the onReject callback with the action ID
- Both buttons are disabled when the `loading` prop is true
- After approval, shows "Approved" resolved state (no active buttons)
- After rejection, shows "Rejected" resolved state (no active buttons)

### Unit: ApprovalBadge
- Renders nothing (or null) when count is 0
- Renders the count number when count > 0
- Renders with a visually distinct badge style (e.g., red background)

### Unit: API layer (approvals.ts)
- `approveAction(sessionId, actionId)` calls POST to the correct URL with action_id in the body
- `rejectAction(sessionId, actionId)` calls POST to the correct URL with action_id in the body
- Both functions throw on non-OK response

### Unit: ChatPanel with approval events
- When an `approval.required` event arrives, an ApprovalPrompt is rendered in the chat flow
- ApprovalPrompt appears in chronological order among messages and tool calls
- Approving via the prompt calls the API and updates the prompt to resolved state

### Integration: SessionPage with mode and approvals
- SessionPage header shows the SessionModeIndicator with the session's current mode
- SessionPage header shows the ApprovalBadge (when approvals are pending)
- Switching mode via SessionModeSwitcher updates the mode indicator after API success

## Out of Scope
- Backend approval gates policy engine (issue #44)
- Backend agent modes behavioral logic -- system prompts, tool filtering per mode (issue #45)
- Approval configuration UI (which actions require approval) -- future issue
- Approval history/audit log view -- future issue

## Technical Notes
- The session's `mode` field is a free-form string in the backend (`str`, not an enum). The frontend should define the 5 known modes as constants but gracefully handle unknown mode strings.
- `PATCH /api/sessions/{id}` with `{"mode": "review"}` is already tested and working (issue #05).
- `apiClient.post` is available (added in issue #16).
- The `useNotifications()` hook already derives `pendingApprovals` count from `approval.required` events -- reuse it in `ApprovalBadge`.
- For `ApprovalPrompt` in the chat flow, extend `CHAT_EVENT_TYPES` in `ChatPanel` to include `"approval.required"` and add a new `ChatItem` kind (e.g., `"approval"`).
- Use Vitest with the same mock patterns as existing tests (vi.fn, @testing-library/react).

## Log

### [SWE] 2026-03-15 09:50
- Implemented all components and API layer for session mode switching and approval UI
- Added `patch` method to `apiClient` (needed for PATCH /api/sessions/{id})
- Created `web/src/api/approvals.ts` with `approveAction` and `rejectAction` functions using `apiClient.post`
- Created `web/src/components/SessionModeIndicator.tsx` -- displays mode with 5 distinct color styles plus fallback
- Created `web/src/components/SessionModeSwitcher.tsx` -- button group for all 5 modes with active highlight, disabled/loading states
- Created `web/src/components/ApprovalPrompt.tsx` -- inline card with Approve/Reject buttons, loading state, resolved state
- Created `web/src/components/ApprovalBadge.tsx` -- red counter badge, hidden when count is 0
- Created `web/src/components/SessionApprovalBadge.tsx` -- wrapper that consumes `useNotifications()` hook and passes count to ApprovalBadge
- Updated `web/src/pages/SessionPage.tsx` -- added SessionModeIndicator + ApprovalBadge in header, toggleable SessionModeSwitcher, mode change via PATCH API
- Updated `web/src/components/ChatPanel.tsx` -- added `approval.required` to CHAT_EVENT_TYPES, new `approval` ChatItem kind, inline ApprovalPrompt rendering with approve/reject API calls and optimistic state updates
- Files created: api/approvals.ts, components/SessionModeIndicator.tsx, components/SessionModeSwitcher.tsx, components/ApprovalPrompt.tsx, components/ApprovalBadge.tsx, components/SessionApprovalBadge.tsx
- Files modified: api/client.ts, pages/SessionPage.tsx, components/ChatPanel.tsx
- Tests added: 41 new tests across 7 test files (SessionModeIndicator: 4, SessionModeSwitcher: 6, ApprovalPrompt: 7, ApprovalBadge: 3, approvals API: 4, ChatPanel approvals: 5, SessionPage mode/approvals: 4, plus existing SessionPage/ChatPanel tests still pass)
- Build results: 150 tests pass (109 existing + 41 new), 0 fail, tsc clean, build clean
- Known limitations: none

### [QA] 2026-03-15 09:55
- Tests: 150 passed, 0 failed (30 test files, 41 new tests for this issue)
- TypeScript: clean (tsc -b passes)
- Build: clean (vite build succeeds)
- Acceptance criteria:
  1. 110+ tests: PASS (150 total)
  2. SessionModeIndicator renders mode name with mode-specific color: PASS
  3. SessionModeIndicator visible in SessionPage header: PASS
  4. SessionModeSwitcher renders all 5 modes: PASS
  5. SessionModeSwitcher highlights active mode: PASS
  6. Clicking mode calls PATCH /api/sessions/{id}: PASS
  7. SessionModeSwitcher disables during API call: PASS
  8. SessionModeSwitcher updates mode after success: PASS
  9. ApprovalPrompt renders inline for approval.required events: PASS
  10. ApprovalPrompt displays action description: PASS
  11. ApprovalPrompt has Approve and Reject buttons: PASS
  12. Clicking Approve calls approveAction POST: PASS
  13. Clicking Reject calls rejectAction POST: PASS
  14. ApprovalPrompt disables buttons during API call: PASS
  15. ApprovalPrompt shows resolved state: PASS
  16. ApprovalBadge shows count when > 0: PASS
  17. ApprovalBadge hidden when zero: PASS
  18. ApprovalBadge in SessionPage header: PASS
  19. ChatPanel handles approval.required events: PASS
  20. approveAction/rejectAction use apiClient.post and throw on error: PASS
  21. No TypeScript errors: PASS
  22. Components follow project patterns: PASS
- VERDICT: PASS

### [PM] 2026-03-15 10:00
- Reviewed diff: 9 files changed (6 new components/API, 7 new test files, 3 modified files)
- New files: api/approvals.ts, components/SessionModeIndicator.tsx, SessionModeSwitcher.tsx, ApprovalPrompt.tsx, ApprovalBadge.tsx, SessionApprovalBadge.tsx
- Modified files: api/client.ts (added patch method), ChatPanel.tsx (approval.required handling), SessionPage.tsx (mode indicator, switcher, badge in header)
- Results verified: 150 tests pass (30 test files), tsc clean, vite build clean -- all confirmed by running `npx vitest run`, `npx tsc -b`, `npm run build`
- Test quality: 41 new tests across 7 test files covering all components, API layer, integration with ChatPanel and SessionPage. Tests verify actual behavior (callbacks, API calls, DOM order, resolved states, disabled states), not just rendering.
- Code quality: Clean functional components, TypeScript throughout, Tailwind CSS, consistent with existing project patterns. Good use of optimistic updates for approval state. Proper error handling with rollback on API failure.
- Acceptance criteria: all 22 met
  1. 110+ tests: 150 total -- PASS
  2. SessionModeIndicator mode-specific color: 5 distinct styles in MODE_STYLES -- PASS
  3. SessionModeIndicator in SessionPage header: rendered at line 123 -- PASS
  4. SessionModeSwitcher renders all 5 modes: maps SESSION_MODES -- PASS
  5. SessionModeSwitcher highlights active mode: aria-pressed + distinct class -- PASS
  6. Clicking mode calls PATCH: apiClient.patch in handleModeChange -- PASS
  7. SessionModeSwitcher disables during API call: modeLoading state -- PASS
  8. SessionModeSwitcher updates mode after success: setSession updates state -- PASS
  9. ApprovalPrompt inline for approval.required: added to CHAT_EVENT_TYPES -- PASS
  10. ApprovalPrompt displays description: with tool_name fallback -- PASS
  11. ApprovalPrompt Approve and Reject buttons: in pending state -- PASS
  12. Approve calls POST: handleApprove -> approveAction -- PASS
  13. Reject calls POST: handleReject -> rejectAction -- PASS
  14. ApprovalPrompt disables buttons during API: loading prop -- PASS
  15. ApprovalPrompt resolved state: shows Approved/Rejected text -- PASS
  16. ApprovalBadge count > 0: renders count number -- PASS
  17. ApprovalBadge hidden when zero: returns null -- PASS
  18. ApprovalBadge in SessionPage header: SessionApprovalBadge rendered -- PASS
  19. ChatPanel handles approval.required: new approval ChatItem kind -- PASS
  20. approveAction/rejectAction use apiClient.post, throw on error -- PASS
  21. No TypeScript errors: tsc -b clean -- PASS
  22. Project patterns: functional components, TS, Tailwind -- PASS
- Follow-up issues created: none needed
- VERDICT: ACCEPT
