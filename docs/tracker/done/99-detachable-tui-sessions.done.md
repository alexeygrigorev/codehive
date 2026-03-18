# Issue #99: Detachable TUI sessions -- give task and close terminal

## Problem

Currently `codehive code` runs the engine in-process. If you close the terminal, the session dies. When connected to the backend, the session should continue running server-side after the TUI disconnects -- like tmux but for agent sessions.

## Dependencies

- #94b (`codehive code` connects to backend) must be `.done.md` -- the TUI must already use the backend API for message sending. Without backend mode, there is no server-side engine to keep running.
- #94c (cross-client session visibility) should be `.done.md` -- WebSocket streaming of engine events to connected clients is the foundation for live resume.

## Scope

This issue has three parts: (A) making `POST /api/sessions/{id}/messages` non-blocking so the engine runs asynchronously, (B) loading history on reconnect, and (C) resuming live streaming mid-run.

### Part A: Non-blocking message dispatch (backend)

Currently `POST /api/sessions/{id}/messages` runs the engine synchronously and returns all events as a JSON array. This means the HTTP request blocks until the agent finishes (which can take minutes). The TUI cannot disconnect during this time without killing the request.

1. **New endpoint: `POST /api/sessions/{id}/messages/async`** (or modify existing endpoint with a query param `?async=true`)
   - Accepts `{"content": "..."}` like the existing endpoint
   - Starts the engine run as a background task (`asyncio.create_task` or similar)
   - Returns immediately with `202 Accepted` and `{"status": "running"}`
   - The engine run stores messages/events in DB and publishes to Redis as it goes (existing EventBus behavior)
   - Session status transitions to `executing` when the run starts, and back to `idle` (or `completed`/`failed`) when it finishes

2. **Session status tracking:**
   - `GET /api/sessions/{id}` already returns `status` -- use this to check if the agent is still running
   - The background engine task must update session status in DB when it starts and finishes

3. **Engine lifecycle management:**
   - The background task must be tracked so the server can clean up on shutdown
   - If the session already has a running engine task, reject new messages with `409 Conflict`

### Part B: History loading on reconnect (TUI)

4. **On connect in backend mode, CodeApp loads session history:**
   - Call `GET /api/sessions/{id}/transcript?format=json` to get all past messages and tool calls
   - Render each entry in the chat scroll area (messages as chat bubbles, tool calls as tool bubbles)
   - Show a separator line: `--- reconnected ---` between historical messages and new ones

5. **Session status check on connect:**
   - Call `GET /api/sessions/{id}` to get current status
   - If `status == "idle"` or `status == "completed"`: show history, ready for new input
   - If `status == "executing"`: show history, then connect WebSocket for live events (Part C)
   - If `status == "failed"`: show history, show error status, ready for new input

### Part C: Live streaming resume (TUI)

6. **WebSocket connection for live events:**
   - After loading history, if session is still running, connect to `WS /api/sessions/{id}/ws`
   - Render incoming events in real-time (same rendering logic as current `_run_agent`)
   - When the engine finishes (session status changes to `idle`/`completed`), the WebSocket stream ends naturally

7. **Status indicator in the TUI status bar:**
   - `"reconnected (loading history...)"` while loading transcript
   - `"reconnected (catching up)"` while replaying history and agent is still running
   - `"connected (live)"` when WebSocket is streaming live events
   - `"idle"` when agent is not running
   - Current `"thinking..."` / `"streaming..."` indicators remain for messages sent in the current session

8. **Deduplication:**
   - History loaded via transcript may overlap with events arriving via WebSocket
   - Use message/event timestamps or IDs to skip events that were already rendered from history
   - Simple approach: record the latest `created_at` from history, skip WebSocket events with earlier timestamps

### What is NOT in scope

- Local-only mode: session dies with the process, no detach support. This is expected behavior and should show a warning if the user tries to rely on it.
- Multiple concurrent TUI clients on the same session: only one client sends messages at a time. Multiple viewers via WebSocket is already handled by the existing infrastructure.
- Fire-and-forget CLI mode (`codehive send "do X" && exit`): that is a separate issue.

## Acceptance Criteria

- [ ] `POST /api/sessions/{id}/messages/async` (or `?async=true`) returns `202 Accepted` immediately and runs the engine in the background
- [ ] The background engine task updates session `status` to `executing` on start and `idle`/`completed`/`failed` on finish
- [ ] A second `POST /api/sessions/{id}/messages/async` while the engine is running returns `409 Conflict`
- [ ] Engine events are stored in DB and published to Redis during background execution (existing EventBus behavior, verified working)
- [ ] `codehive code` in backend mode: on connect, loads session transcript and renders history in the chat area
- [ ] If the session has no history (new session), no transcript is loaded, input is ready immediately
- [ ] If the session status is `executing` on connect, the TUI connects to the WebSocket and streams live events after history
- [ ] If the session status is `idle`/`completed` on connect, the TUI shows history and is ready for new input
- [ ] After sending a message, the TUI connects to the WebSocket to receive live events (instead of waiting for the HTTP response)
- [ ] Closing the TUI (`Ctrl+Q`, terminal close) does NOT stop the backend engine -- it keeps running
- [ ] Reopening `codehive code` (same session) shows all messages that occurred while disconnected
- [ ] Status bar shows appropriate indicator: `"reconnected (loading history...)"`, `"connected (live)"`, `"idle"`
- [ ] Historical messages and live events are not duplicated in the chat area
- [ ] `cd backend && uv run pytest tests/ -v` passes with 10+ new tests
- [ ] `cd backend && uv run ruff check` passes

## Test Scenarios

### Unit: Async message dispatch (`test_async_message_dispatch.py`)
- `POST /api/sessions/{id}/messages/async` with valid session returns 202 and `{"status": "running"}`
- Session status changes to `executing` after the async dispatch
- A second `POST /api/sessions/{id}/messages/async` while running returns 409
- After the engine finishes, session status is `idle` or `completed`
- Events are persisted to the DB during the background run (query `events` table)
- Invalid session ID returns 404

### Unit: History loading (`test_history_loading.py`)
- CodeApp in backend mode calls `GET /api/sessions/{id}/transcript?format=json` on mount
- Transcript entries are rendered in order: user messages as user bubbles, assistant messages as assistant bubbles, tool calls as tool bubbles
- Empty transcript (new session) results in no history rendering, input is ready
- Transcript loading error (e.g. 500) shows error in status bar, does not crash

### Unit: Reconnect with running session (`test_reconnect_running.py`)
- Session status is `executing`: after loading history, TUI opens WebSocket to `/api/sessions/{id}/ws`
- WebSocket events are rendered in real-time after history
- When engine finishes (WebSocket closes or status event received), status bar updates to `idle`

### Unit: Reconnect with finished session (`test_reconnect_finished.py`)
- Session status is `idle`: history is loaded, no WebSocket connection opened
- Session status is `completed`: history is loaded, status shown as completed
- Session status is `failed`: history is loaded, error indicator shown

### Unit: Deduplication (`test_event_deduplication.py`)
- History contains events up to timestamp T1, WebSocket sends event at T1 (duplicate) -- it is skipped
- WebSocket sends event at T2 > T1 -- it is rendered
- Events with matching IDs are deduplicated regardless of timestamp

### Unit: TUI disconnect does not stop backend (`test_detach_backend_continues.py`)
- Start async message dispatch, verify engine task is running
- Simulate TUI disconnect (close WebSocket, no further API calls)
- Verify engine task is still running (session status still `executing`)
- Verify engine task completes and session status becomes `idle`

### Integration: Full detach/reattach cycle
- Send a message via async dispatch, disconnect TUI
- Reconnect: verify history includes the message and response
- Verify status indicator shows `"reconnected (loading history...)"` then transitions appropriately

## Log

### [SWE] 2026-03-18 10:50
- Implemented all three parts: async dispatch (A), history loading (B), live streaming resume (C)
- Part A: New endpoint POST /api/sessions/{id}/messages/async in a separate route file (async_dispatch.py) to avoid conflicts with #94c. Returns 202 Accepted, runs engine as asyncio background task. Rejects 409 if already running. Updates session status to executing/waiting_input/failed. Task registry with shutdown cleanup.
- Part B: CodeApp._load_backend_session() loads transcript via GET /api/sessions/{id}/transcript?format=json on mount. Renders user/assistant messages and tool calls. Shows "--- reconnected ---" separator. Empty transcript shows normal start message.
- Part C: If session status is "executing" on connect, starts WebSocket listener (_stream_ws_events) for live events. Deduplication by timestamp comparison. Fallback to polling if websockets library unavailable. Status bar indicators: "reconnected (loading history...)", "connected (live)", "idle".
- Backend mode now uses async dispatch + WebSocket instead of synchronous POST, so engine survives TUI disconnect.
- Files modified:
  - backend/codehive/api/routes/async_dispatch.py (NEW - async dispatch endpoint + background task management)
  - backend/codehive/api/app.py (register async_dispatch_router, add shutdown cleanup)
  - backend/codehive/clients/terminal/code_app.py (history loading, WebSocket streaming, async dispatch, deduplication)
- Files created:
  - backend/tests/test_async_dispatch.py (9 tests: 202 response, 404, 409 conflict, executing status, waiting_input after completion, failed on error, disconnect resilience, task cleanup, full lifecycle)
  - backend/tests/test_detachable_sessions.py (16 tests: history loading, empty transcript, error handling, executing/idle/failed/completed reconnect, deduplication, WS event processing, async dispatch from TUI, transcript rendering)
- Tests added: 25 new tests across 2 files
- Build results: 1747 tests pass, 0 fail, ruff clean
- Known limitations: WebSocket streaming requires the `websockets` library (falls back to polling if not available). cli.py was not modified (no changes needed -- existing _code() function already handles session resolution).

## Implementation Notes

- The existing `POST /api/sessions/{id}/messages` endpoint can remain as-is for backward compatibility (web clients may use it synchronously). The new async variant is specifically for the detachable TUI workflow.
- The transcript endpoint (`GET /api/sessions/{id}/transcript?format=json`) already returns messages and tool calls in chronological order -- this is the history source.
- The WebSocket endpoint (`WS /api/sessions/{id}/ws`) already streams events from the Redis event bus -- this is the live source.
- The main new backend work is the async message dispatch and background task management. The TUI work is connecting the existing pieces (transcript + WebSocket) in the right order.
- For background task tracking, consider a dict `_running_tasks: dict[uuid.UUID, asyncio.Task]` on the app or a dedicated service. On server shutdown (`@app.on_event("shutdown")`), cancel running tasks gracefully.
- Auth handling: same as #94b -- when `auth_enabled=False`, endpoints work without tokens. WebSocket auth uses query param token or first-message auth (existing).
