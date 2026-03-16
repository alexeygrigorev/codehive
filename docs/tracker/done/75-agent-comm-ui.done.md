# 75: Agent Communication UI

## Description

Web UI for viewing agent-to-agent communication within the session view. This issue adds two capabilities:

1. **Agent Messages Panel** -- A new sidebar tab ("Comms") that shows all `agent.message` and `agent.query` events for a session, rendered as a conversation view. Each message shows the sender/target session name, the message content, and timestamp.

2. **Inline agent message indicators in SubAgentNode** -- Each node in the sub-agent tree shows a small badge/count of unread agent messages, so the user can see at a glance which agents are actively communicating.

The backend already has the `agent.message` and `agent.query` event types stored in the events table (from #62). The existing `GET /api/sessions/{session_id}/events` endpoint returns all events. This issue is purely frontend: fetch events, filter for agent communication types, and render them in a dedicated UI.

## Scope

### New files
- `web/src/api/agentComm.ts` -- API client functions: `fetchAgentMessages(sessionId)` that calls `GET /api/sessions/{sessionId}/events` and filters for `agent.message` and `agent.query` event types client-side. Returns `AgentCommEvent[]`.
- `web/src/components/sidebar/AgentCommPanel.tsx` -- Sidebar panel component that accepts `sessionId` prop, fetches agent comm events, and renders them as a conversation. Follows the same loading/error/empty pattern as `TodoPanel` and `SubAgentPanel`.
- `web/src/components/AgentMessageItem.tsx` -- Individual agent message display. Shows: sender session name (from `event.data.sender_session_id`), direction indicator (incoming/outgoing), message text, and timestamp. For `agent.query` events, shows "queried [session name]" with the query result summary.
- `web/src/test/agentComm.test.ts` -- Tests for the API client function.
- `web/src/test/AgentCommPanel.test.tsx` -- Tests for the panel component.
- `web/src/test/AgentMessageItem.test.tsx` -- Tests for the message item component.

### Modified files
- `web/src/components/sidebar/SidebarTabs.tsx` -- Add a "Comms" tab that renders `AgentCommPanel` with the `sessionId` prop. Place it after the "Sub-agents" tab.
- `web/src/components/SubAgentNode.tsx` -- Add an optional `messageCount` prop. When > 0, display a small numeric badge next to the session name showing the count of agent messages for that sub-agent.
- `web/src/test/SidebarTabs.test.tsx` -- Add test for the new "Comms" tab.
- `web/src/test/SubAgentNode.test.tsx` -- Add test for message count badge.

## Dependencies
- Depends on: #62 (agent communication backend) -- DONE
- Depends on: #23 (sub-agent tree view) -- DONE

## Acceptance Criteria

- [ ] `web/src/api/agentComm.ts` exports `fetchAgentMessages(sessionId: string): Promise<AgentCommEvent[]>` that calls `GET /api/sessions/${sessionId}/events` and filters results to only `agent.message` and `agent.query` event types
- [ ] `AgentCommEvent` type is exported with fields: `id`, `session_id`, `type` ("agent.message" | "agent.query"), `data` (containing `sender_session_id`, `target_session_id`, `message`, `timestamp`), `created_at`
- [ ] `AgentCommPanel` accepts a `sessionId: string` prop (matching the pattern of `TodoPanel`, `SubAgentPanel`)
- [ ] `AgentCommPanel` shows a loading state while the API call is in-flight
- [ ] `AgentCommPanel` shows an error message when the fetch fails
- [ ] `AgentCommPanel` shows an empty state ("No agent communications" or similar) when there are no agent.message or agent.query events
- [ ] `AgentCommPanel` renders one `AgentMessageItem` per agent comm event when events exist
- [ ] `AgentMessageItem` displays the sender session ID (or name if available in event data), message text, and a human-readable timestamp
- [ ] `AgentMessageItem` visually distinguishes `agent.message` events from `agent.query` events (different icon, label, or styling)
- [ ] `AgentMessageItem` visually distinguishes incoming messages (where session is the target) from outgoing messages (where session is the sender) using alignment or color, similar to how `MessageBubble` uses `data-role` styling
- [ ] `AgentMessageItem` has a `data-type` attribute on the root element set to the event type (for testability)
- [ ] `SidebarTabs` includes a "Comms" tab that renders `AgentCommPanel` with `sessionId` passed through
- [ ] `SubAgentNode` accepts an optional `messageCount?: number` prop and renders a badge (e.g., small colored circle with number) when `messageCount > 0`
- [ ] `SubAgentNode` does not render the badge when `messageCount` is 0 or undefined
- [ ] `cd /home/alexey/git/codehive/web && npx vitest run` passes with all existing tests plus 14+ new tests for agent communication UI
- [ ] No regressions: all pre-existing web tests continue to pass

## Test Scenarios

### Unit: fetchAgentMessages API function (`web/src/test/agentComm.test.ts`)
- Call `fetchAgentMessages("session-1")` with a mocked successful response containing 5 events (3 agent.message, 1 agent.query, 1 file.changed). Verify it returns only the 4 agent comm events (filters out file.changed).
- Call `fetchAgentMessages("session-1")` with a mocked successful response containing 0 events. Verify it returns an empty array.
- Call `fetchAgentMessages("session-1")` with a mocked 500 response. Verify it throws an error.

### Unit: AgentCommPanel (`web/src/test/AgentCommPanel.test.tsx`)
- Render with `sessionId="s1"` while fetch is pending. Verify loading text is displayed.
- Render with `sessionId="s1"`, mock returning an empty array. Verify empty state text is displayed.
- Render with `sessionId="s1"`, mock returning 3 agent.message events. Verify all 3 messages are rendered (check for message text content).
- Render with `sessionId="s1"`, mock returning events of both types. Verify both agent.message and agent.query items are rendered with correct `data-type` attributes.
- Render with `sessionId="s1"`, mock fetch rejecting. Verify error message is displayed.

### Unit: AgentMessageItem (`web/src/test/AgentMessageItem.test.tsx`)
- Render with an `agent.message` event where the current session is the target. Verify the item has `data-type="agent.message"` and displays the message text.
- Render with an `agent.message` event where the current session is the sender. Verify outgoing styling is applied (different alignment or color class).
- Render with an `agent.query` event. Verify the item has `data-type="agent.query"` and is visually distinct from message events.
- Render with a timestamp. Verify a human-readable time string is displayed.

### Unit: SidebarTabs Comms tab (`web/src/test/SidebarTabs.test.tsx`)
- Verify that a "Comms" tab exists and clicking it renders `AgentCommPanel` with the `sessionId` prop.

### Unit: SubAgentNode message badge (`web/src/test/SubAgentNode.test.tsx`)
- Render a SubAgentNode with `messageCount={3}`. Verify a badge element with text "3" is visible.
- Render a SubAgentNode with `messageCount={0}`. Verify no badge element is rendered.

## Implementation Notes

- The `fetchAgentMessages` function should reuse the existing `fetchEvents` pattern from `web/src/api/events.ts` but add client-side filtering for `type === "agent.message" || type === "agent.query"`. Alternatively, if the backend `GET /api/sessions/{id}/events` endpoint supports a `type` query parameter for filtering, use that -- but check first. If not, filter client-side.
- `AgentCommPanel` should follow the exact same loading/error/empty state pattern as `SubAgentPanel` (useEffect with cancellation, three-state rendering).
- `AgentMessageItem` styling should follow `MessageBubble` conventions: use `data-type` attribute for testability, use Tailwind classes for visual differentiation.
- For the `SubAgentNode` message count badge, use a small rounded element with a background color (e.g., `bg-blue-500 text-white text-xs rounded-full`) positioned next to the session name.
- Real-time updates for agent messages are out of scope for this issue. The panel loads data on mount. WebSocket-based live updates can be added in a follow-up.

## Log

### [SWE] 2026-03-16 16:48
- Implemented agent communication UI with all acceptance criteria met
- Created `web/src/api/agentComm.ts`: exports `AgentCommEvent` type and `fetchAgentMessages()` that fetches events and filters for agent.message/agent.query types client-side
- Created `web/src/components/AgentMessageItem.tsx`: displays sender/target, message text, timestamp, with visual distinction between message vs query (yellow border + label) and incoming vs outgoing (alignment/color)
- Created `web/src/components/sidebar/AgentCommPanel.tsx`: follows SubAgentPanel loading/error/empty pattern with useEffect cancellation
- Modified `web/src/components/sidebar/SidebarTabs.tsx`: added "Comms" tab (8th tab) after "Sub-agents", renders AgentCommPanel with sessionId
- Modified `web/src/components/SubAgentNode.tsx`: added optional `messageCount` prop with blue rounded badge when > 0
- Files modified: SidebarTabs.tsx, SubAgentNode.tsx
- Files created: agentComm.ts, AgentCommPanel.tsx, AgentMessageItem.tsx, agentComm.test.ts, AgentCommPanel.test.tsx, AgentMessageItem.test.tsx
- Tests added: 17 new tests (3 API, 5 panel, 4 message item, 1 sidebar tab, 3 SubAgentNode badge + 1 updated tab count test)
- Build results: 475 tests pass, 0 fail; TypeScript build clean; 94 test files all pass
- Known limitations: none

### [QA] 2026-03-16 16:55
- Tests: 475 passed, 0 failed (94 test files)
- New tests: 16 new tests (3 API client, 5 panel, 4 message item, 1 sidebar tab, 3 SubAgentNode badge) plus 1 updated test
- Acceptance criteria:
  - fetchAgentMessages exports and filters for agent.message/agent.query: PASS
  - AgentCommEvent type exported with correct fields: PASS
  - AgentCommPanel accepts sessionId prop: PASS
  - AgentCommPanel loading state: PASS
  - AgentCommPanel error state: PASS
  - AgentCommPanel empty state: PASS
  - AgentCommPanel renders AgentMessageItem per event: PASS
  - AgentMessageItem displays sender, message text, timestamp: PASS
  - AgentMessageItem distinguishes agent.message from agent.query: PASS
  - AgentMessageItem distinguishes incoming from outgoing: PASS
  - AgentMessageItem has data-type attribute: PASS
  - SidebarTabs includes Comms tab rendering AgentCommPanel: PASS
  - SubAgentNode accepts messageCount prop, renders badge when > 0: PASS
  - SubAgentNode does not render badge when 0 or undefined: PASS
  - 14+ new tests all passing: PASS (16 new tests)
  - No regressions: PASS (all 475 tests pass)
- VERDICT: PASS

### [PM] 2026-03-16 17:10
- Reviewed diff: 9 tracked files changed + 6 new untracked files (3 source, 3 test)
- New source files: agentComm.ts (API client + type), AgentCommPanel.tsx (sidebar panel), AgentMessageItem.tsx (message display component)
- Modified files: SidebarTabs.tsx (added Comms tab), SubAgentNode.tsx (added messageCount badge)
- New test files: agentComm.test.ts (3 tests), AgentCommPanel.test.tsx (5 tests), AgentMessageItem.test.tsx (4 tests)
- Updated test files: SidebarTabs.test.tsx (+1 test, updated tab count assertion), SubAgentNode.test.tsx (+3 badge tests)
- Results verified: tester confirmed 475 tests pass, 0 failures, 16 new tests
- Code quality: follows existing patterns (SubAgentPanel for loading/error/empty, apiClient for fetch, data-type for testability), proper useEffect cancellation, clean Tailwind styling
- Acceptance criteria: all 16/16 met
- Follow-up issues created: none needed
- VERDICT: ACCEPT
