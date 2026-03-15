# 18: WebSocket Client for Real-Time Updates

## Description
Implement the WebSocket client in the web app that connects to the backend event bus. Provides live message streaming, ToDo status updates, diff updates, and notification badges for pending questions and approvals.

The backend already exposes a WebSocket endpoint at `/api/sessions/{session_id}/ws` (issue #07, done). It publishes JSON messages on Redis pub/sub channel `session:{id}:events` with the structure:

```json
{
  "id": "<uuid>",
  "session_id": "<uuid>",
  "type": "<event_type>",
  "data": { ... },
  "created_at": "<iso8601>"
}
```

Known event types from the product spec and backend code: `message.created`, `tool.call.started`, `tool.call.finished`, `file.changed`, `diff.updated`, `task.started`, `task.completed`, `approval.required`, `session.waiting`, `session.failed`.

## Scope
- `web/src/api/websocket.ts` -- WebSocket connection manager (connect, disconnect, auto-reconnect with exponential backoff, subscribe to session events)
- `web/src/hooks/useSessionEvents.ts` -- React hook for subscribing to a session's event stream; returns an array of received events
- `web/src/hooks/useNotifications.ts` -- React hook that derives notification counts (pending questions, pending approvals) from the event stream
- `web/src/context/WebSocketContext.tsx` -- React context provider that holds the shared WebSocket connection per session and distributes events to subscribers

## Dependencies
- Depends on: #14 (React app scaffolding) -- DONE
- Depends on: #07 (backend WebSocket endpoint and event bus) -- DONE

## Acceptance Criteria

- [ ] `cd web && npx vitest run` passes with 12+ new tests (unit + integration) covering the files in scope
- [ ] `web/src/api/websocket.ts` exports a `WebSocketClient` class (or factory) with `connect(sessionId)`, `disconnect()`, `onEvent(callback)`, and `removeListener(callback)` methods
- [ ] The WebSocket URL is derived from the existing `VITE_API_BASE_URL` env var (converting `http(s)` to `ws(s)`), defaulting to `ws://localhost:8000`
- [ ] Auto-reconnect is implemented with exponential backoff (starting at 1s, capped at 30s) and resets on successful connection
- [ ] `web/src/context/WebSocketContext.tsx` exports a `WebSocketProvider` component and a `useWebSocket()` context hook
- [ ] `WebSocketProvider` accepts a `sessionId` prop (or null) and manages exactly one WebSocket connection per mounted provider; cleans up on unmount or sessionId change
- [ ] `web/src/hooks/useSessionEvents.ts` exports a `useSessionEvents()` hook that returns received events as an array, filtering optionally by event type(s)
- [ ] `web/src/hooks/useNotifications.ts` exports a `useNotifications()` hook that returns `{ pendingQuestions: number, pendingApprovals: number }` derived from events of type `approval.required` and `session.waiting`
- [ ] Event messages are parsed as JSON; malformed messages are silently dropped (logged to console.warn) without crashing
- [ ] Connection state is exposed: `"connecting" | "connected" | "disconnected" | "reconnecting"`
- [ ] No external WebSocket libraries are added -- use the browser-native `WebSocket` API

## Test Scenarios

### Unit: WebSocket connection manager (`websocket.ts`)
- `connect(sessionId)` opens a WebSocket to `ws://localhost:8000/api/sessions/{sessionId}/ws`
- `onEvent(callback)` registers a listener; listener receives parsed event objects when a message arrives
- `removeListener(callback)` unregisters a listener; it no longer receives events
- Calling `disconnect()` closes the WebSocket and stops reconnection attempts
- When the socket closes unexpectedly, reconnect is attempted after an increasing delay (1s, 2s, 4s, ..., capped at 30s)
- On successful reconnect, the backoff delay resets to 1s
- Malformed (non-JSON) messages trigger `console.warn` and do not call event listeners
- Calling `connect()` while already connected closes the previous connection first

### Unit: useSessionEvents hook
- Returns an empty array initially
- Accumulates events as they arrive from the WebSocket
- When given a type filter (e.g., `["message.created"]`), only returns matching events
- Clears events when the session changes

### Unit: useNotifications hook
- Returns `{ pendingQuestions: 0, pendingApprovals: 0 }` when no relevant events exist
- Increments `pendingApprovals` for each `approval.required` event
- Increments `pendingQuestions` for each event with type `session.waiting` where `data.reason` is `"pending_question"`

### Integration: WebSocketProvider context
- Mounting `WebSocketProvider` with a sessionId creates a WebSocket connection
- Unmounting the provider closes the WebSocket connection
- Changing the sessionId prop closes the old connection and opens a new one
- Child components using `useWebSocket()` receive connection state and events
- Using `useWebSocket()` outside of a provider throws a descriptive error

## Out of Scope
- Wiring into `SessionPage.tsx` or other existing pages (will be done in #16 and #17)
- Sending messages from client to server over WebSocket (the backend endpoint is read-only / server-to-client push)
- Authentication / token-based WebSocket handshake (no auth system exists yet)

## Technical Notes
- Use Vitest with `vi.fn()` / `vi.spyOn()` mocks for the native `WebSocket` API, consistent with the existing test patterns in `web/src/test/`
- The existing `apiClient.baseURL` in `web/src/api/client.ts` provides the base URL; derive the WS URL from it
- React Testing Library (`@testing-library/react`) is already available for hook/component testing

## Log

### [SWE] 2026-03-15 09:05
- Implemented all four files in scope:
  - `web/src/api/websocket.ts` -- WebSocketClient class with connect/disconnect/onEvent/removeListener, exponential backoff reconnect (1s-30s), state tracking, malformed message handling
  - `web/src/context/WebSocketContext.tsx` -- WebSocketProvider component and useWebSocket hook; manages one connection per session, cleans up on unmount/sessionId change
  - `web/src/hooks/useSessionEvents.ts` -- useSessionEvents hook returning events array with optional type filtering
  - `web/src/hooks/useNotifications.ts` -- useNotifications hook deriving pendingQuestions and pendingApprovals counts
- WS URL derived from apiClient.baseURL by replacing http(s) with ws(s)
- Used browser-native WebSocket only, no external libraries added
- Tests added: 25 new tests across 4 test files
  - `web/src/test/websocket.test.ts` (11 tests) -- connection manager unit tests
  - `web/src/test/WebSocketContext.test.tsx` (5 tests) -- provider integration tests
  - `web/src/test/useSessionEvents.test.tsx` (4 tests) -- hook unit tests
  - `web/src/test/useNotifications.test.tsx` (4 tests) -- hook unit tests + edge case for non-matching session.waiting reason
- Build results: 60 tests pass (25 new + 35 existing), 0 fail, tsc clean, vite build clean
- Files created:
  - web/src/api/websocket.ts
  - web/src/context/WebSocketContext.tsx
  - web/src/hooks/useSessionEvents.ts
  - web/src/hooks/useNotifications.ts
  - web/src/test/websocket.test.ts
  - web/src/test/WebSocketContext.test.tsx
  - web/src/test/useSessionEvents.test.tsx
  - web/src/test/useNotifications.test.tsx
- Known limitations: none

### [QA] 2026-03-15 09:10
- Tests: 60 passed (25 new + 35 existing), 0 failed
- TypeScript: clean (tsc --noEmit passes)
- Build: clean (vite build succeeds)
- Acceptance criteria:
  1. 12+ new tests passing: PASS (25 new tests)
  2. WebSocketClient class with connect/disconnect/onEvent/removeListener: PASS
  3. WS URL derived from VITE_API_BASE_URL, defaults to ws://localhost:8000: PASS
  4. Exponential backoff 1s-30s, resets on success: PASS
  5. WebSocketProvider and useWebSocket exports: PASS
  6. Provider manages one connection, cleans up on unmount/sessionId change: PASS
  7. useSessionEvents with optional type filtering: PASS
  8. useNotifications returns pendingQuestions/pendingApprovals: PASS
  9. Malformed messages logged via console.warn, do not crash: PASS
  10. Connection state exposed (connecting/connected/disconnected/reconnecting): PASS
  11. No external WebSocket libraries: PASS
- VERDICT: PASS

### [PM] 2026-03-15 09:15
- Reviewed diff: 8 new files (4 source + 4 test), all untracked
- Results verified: real data present -- 60 tests pass (25 new + 35 existing), tsc clean, vite build clean
- Code review:
  - WebSocketClient: correct exponential backoff (1s/2s/4s/.../30s cap), reset on success, proper cleanup of handlers before close, malformed JSON handled gracefully
  - WebSocketProvider: single connection per sessionId via useEffect dependency, events cleared on session change, cleanup disconnects on unmount
  - useSessionEvents: useMemo with Set-based type filtering, returns full array when no filter
  - useNotifications: correctly derives counts from approval.required and session.waiting (with reason=pending_question check)
  - Tests are substantive: verify reconnection timing, backoff progression, state transitions, event accumulation/filtering, provider lifecycle, error cases
  - No external dependencies added; browser-native WebSocket only
  - URL derivation correctly uses apiClient.baseURL with http(s)->ws(s) conversion
- Acceptance criteria: all 11 met
  1. 12+ new tests: PASS (25 new tests)
  2. WebSocketClient with connect/disconnect/onEvent/removeListener: PASS
  3. WS URL from VITE_API_BASE_URL, defaults to ws://localhost:8000: PASS
  4. Exponential backoff 1s-30s, resets on success: PASS
  5. WebSocketProvider and useWebSocket exports: PASS
  6. Provider manages one connection, cleans up on unmount/sessionId change: PASS
  7. useSessionEvents with optional type filtering: PASS
  8. useNotifications returns pendingQuestions/pendingApprovals: PASS
  9. Malformed messages logged via console.warn, no crash: PASS
  10. Connection state exposed (connecting/connected/disconnected/reconnecting): PASS
  11. No external WebSocket libraries: PASS
- Follow-up issues created: none needed
- VERDICT: ACCEPT
