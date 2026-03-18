# Issue #100: Session persistence and recovery after restart

## Problem

If the codehive process is killed while sessions are actively executing (agent mid-conversation, running tools, etc.), all in-flight work is lost. When the server restarts, those sessions show as "executing" in the DB but nothing is actually running. There's no mechanism to detect and resume interrupted sessions.

## Dependencies

- None for core implementation. Issue #99 (detachable sessions) is related but not blocking -- this issue can be built independently and #99 can integrate with it later.

## Scope

This issue covers backend-only changes: session status lifecycle, startup recovery, graceful shutdown, and resume API endpoint. UI changes (showing interrupted sessions prominently in web/TUI) are out of scope and should be tracked separately.

## Requirements

### Session status lifecycle
- [ ] Add `interrupted` as a valid session status (alongside existing `idle`, `planning`, `executing`, `waiting_input`, `blocked`, `completed`, `failed`)
- [ ] When a user sends a message and the engine starts processing, set session status to `executing`
- [ ] When the engine finishes a turn (no more tool calls, final text response emitted), set session status to `waiting_input`
- [ ] When a session completes (explicitly ended or task queue drained), set status to `completed`
- [ ] When the engine encounters an unrecoverable error, set status to `failed`

### Startup recovery
- [ ] In the app lifespan (startup), query all sessions with status `executing`
- [ ] Update their status to `interrupted` -- they were mid-execution when the process died
- [ ] Log the number of interrupted sessions at startup (INFO level)

### Graceful shutdown
- [ ] Register a SIGTERM/SIGINT handler in the app lifespan
- [ ] On shutdown signal, query all sessions with status `executing` and mark them as `interrupted`
- [ ] Commit the status changes to DB before the process exits

### Resume API endpoint
- [ ] `POST /api/sessions/{session_id}/resume-interrupted` resumes an interrupted session
- [ ] Only allowed when session status is `interrupted` -- return 409 otherwise
- [ ] Loads the last user message from the `messages` table (most recent where `role='user'`)
- [ ] Sets session status to `executing`
- [ ] Re-sends the last user message to the engine (same as `send_message`)
- [ ] Returns the session object with updated status

### Core business logic
- [ ] Add `mark_interrupted_sessions()` async function in `core/session.py` -- bulk updates all `executing` sessions to `interrupted`, returns count
- [ ] Add `resume_interrupted_session()` async function in `core/session.py` -- validates status is `interrupted`, fetches last user message, transitions to `executing`
- [ ] Update `_PAUSABLE_STATUSES` and `resume_session()` to also allow resuming from `interrupted` (or keep them separate -- `resume` for `blocked`, `resume-interrupted` for `interrupted`)

## Acceptance Criteria

- [ ] `uv run pytest tests/ -v` passes with 8+ new tests
- [ ] `uv run ruff check` passes clean
- [ ] Session status transitions to `executing` when engine starts processing a message
- [ ] Session status transitions to `waiting_input` when engine finishes a turn
- [ ] On app startup, sessions stuck in `executing` are automatically marked `interrupted`
- [ ] On SIGTERM, sessions in `executing` status are marked `interrupted` before exit
- [ ] `POST /api/sessions/{id}/resume-interrupted` on an `interrupted` session returns 200 and re-sends the last user message
- [ ] `POST /api/sessions/{id}/resume-interrupted` on a non-interrupted session returns 409
- [ ] `mark_interrupted_sessions()` correctly bulk-updates only `executing` sessions
- [ ] Startup recovery is logged at INFO level with count of interrupted sessions

## Test Scenarios

### Unit: mark_interrupted_sessions
- Create 3 sessions: one `executing`, one `idle`, one `completed`
- Call `mark_interrupted_sessions()` -- verify only the `executing` one becomes `interrupted`
- Call again -- verify it returns 0 (no sessions to mark)

### Unit: resume_interrupted_session
- Create a session with status `interrupted` and add messages (user + assistant + user)
- Call `resume_interrupted_session()` -- verify status becomes `executing` and last user message is returned
- Attempt to resume a session with status `idle` -- verify `InvalidStatusTransitionError` is raised
- Attempt to resume an interrupted session that has no user messages -- verify appropriate error

### Unit: session status transitions
- Verify that `interrupted` is accepted as a valid session status in the model
- Verify pause/resume state machine does not conflict with the new `interrupted` status

### Integration: startup recovery
- Insert sessions with status `executing` directly in DB
- Trigger the lifespan startup logic
- Verify those sessions now have status `interrupted`

### Integration: graceful shutdown
- Set sessions to `executing` status
- Trigger the lifespan shutdown logic
- Verify sessions are marked `interrupted`

### Integration: resume-interrupted endpoint
- Create a session, set status to `interrupted`, add a user message
- `POST /api/sessions/{id}/resume-interrupted` -- verify 200 response with status `executing`
- Try the same on an `idle` session -- verify 409

### Unit: status transitions during engine execution
- Mock the engine, send a message, verify session status is set to `executing` at start
- Verify session status is set to `waiting_input` when engine completes a turn

## Implementation Notes

- The `Session` model in `db/models.py` uses a `Unicode(50)` for status with server_default `"idle"` -- no enum constraint, so `interrupted` works without migration
- The existing `resume_session()` in `core/session.py` handles `blocked -> idle`. Keep it separate from `resume_interrupted_session()` which handles `interrupted -> executing` with message replay
- The lifespan in `api/app.py` currently only runs first-run seeding on startup. Add recovery logic there.
- Signal handling: use `asyncio.get_event_loop().add_signal_handler()` or handle in the lifespan shutdown phase
- The `NativeEngine._sessions` dict holds in-memory state. On resume, a new `_SessionState` is created and conversation history is rebuilt from DB messages

## Notes

- The conversation history is already persisted in the events table
- The engine's in-memory state (tool call results, pending API response) is lost on crash -- that's acceptable
- The key insight: we're not trying to resume mid-tool-call, just resume the conversation from the last known state
- This ties into #99 (detachable sessions) -- a detached session that finishes normally goes to `completed`, one that crashes goes to `interrupted`

## Log

### [SWE] 2026-03-18 12:00
- Implemented session persistence and recovery after restart
- Added `mark_interrupted_sessions()` -- bulk updates all `executing` sessions to `interrupted`
- Added `resume_interrupted_session()` -- validates `interrupted` status, fetches last user message, transitions to `executing`
- Added `NoUserMessageError` exception for sessions with no user messages to replay
- Updated app lifespan: startup marks executing sessions as interrupted, shutdown does the same
- Added `POST /api/sessions/{id}/resume-interrupted` endpoint (returns 200 on success, 409 on wrong status/no messages, 404 on not found)
- Updated `send_message_endpoint` to set session status to `executing` at start, `waiting_input` when done, `failed` on error
- Files modified:
  - `backend/codehive/core/session.py` -- added `mark_interrupted_sessions()`, `resume_interrupted_session()`, `NoUserMessageError`
  - `backend/codehive/api/app.py` -- added startup recovery and graceful shutdown in lifespan
  - `backend/codehive/api/routes/sessions.py` -- added `resume-interrupted` endpoint, status transitions in `send_message`
- Tests added: 16 tests in `backend/tests/test_session_persistence.py`
  - 4 unit tests for `mark_interrupted_sessions` (marks only executing, returns zero, idempotent, marks multiple)
  - 4 unit tests for `resume_interrupted_session` (happy path, wrong status, no messages, not found)
  - 2 unit tests for interrupted status validity (valid status, not pausable)
  - 2 integration tests for startup/shutdown recovery
  - 4 integration tests for resume-interrupted endpoint (200, 409 wrong status, 404, 409 no messages)
- Build results: 1713 tests pass, 0 fail, 3 skipped, ruff clean
- Known limitations: none
