# Issue #94b: `codehive code` connects to backend when available

Parent: #94

## Problem

`codehive code` currently always runs a standalone NativeEngine with `_NoOpEventBus`. Sessions are invisible to the backend -- web/mobile cannot see them, and session history is lost when the TUI exits. The terminal should be "just another client" connecting to the shared backend.

## Dependencies

- #94a (project-by-path API) must be `.done.md` -- needed to resolve directory to project

## Scope

### CLI changes (`cli.py`)

1. **New flags on `codehive code`:**
   - `--session <uuid>` -- connect to a specific existing session
   - `--new` -- always create a new session (don't resume the latest)
   - Existing flags (`--model`, `--provider`, `--auto-approve`, `directory`) remain unchanged

2. **Backend detection in `_code()`:**
   - Before launching CodeApp, probe `GET /api/system/health` on the configured base URL
   - If reachable: pass `backend_url` to CodeApp
   - If not reachable: print warning "Backend not available, starting local-only session" and launch CodeApp without backend_url (current behavior)

3. **Project/session resolution (when backend is available):**
   - Call `POST /api/projects/by-path {"path": "<abs_directory>"}` to get-or-create the project
   - If `--session <id>` flag: use that session ID directly
   - If `--new` flag: call `POST /api/projects/{project_id}/sessions` to create a new session
   - Otherwise: call `GET /api/projects/{project_id}/sessions` to list sessions, pick the most recent one (by `created_at`). If none exist, create one.
   - Pass `session_id` and `project_id` to CodeApp

### CodeApp changes (`code_app.py`)

4. **Two initialization modes in `_init_engine()`:**
   - **Backend mode** (when `backend_url` is set): engine sends messages via `POST /api/sessions/{id}/messages` and receives events from the response. No local NativeEngine, no local Anthropic client needed.
   - **Local mode** (when `backend_url` is None): current behavior -- local NativeEngine + NoOpEventBus

5. **Backend mode message flow:**
   - `_run_agent()` sends `POST /api/sessions/{session_id}/messages {"content": "..."}` to the backend
   - The backend runs the engine and returns events as a JSON array (existing endpoint behavior)
   - CodeApp iterates over the returned events and renders them in the UI (same event types as local mode)

6. **Constructor changes:**
   - New optional params: `backend_url: str | None`, `session_id: uuid.UUID | None`, `project_id: uuid.UUID | None`
   - When in backend mode, `api_key` / `base_url` / `model` are not needed (backend has its own config)

### Tests

7. **Unit tests:**
   - Backend detection: mock health endpoint returning 200 -> backend mode; connection error -> local mode
   - Project resolution: mock by-path API -> returns project
   - Session resolution: mock sessions list -> picks most recent; empty list -> creates new session
   - `--session` flag overrides session resolution
   - `--new` flag forces new session creation

8. **Integration tests (if backend is testable):**
   - `codehive code /tmp/testdir` with backend running -> creates project + session, connects
   - `codehive code --new /tmp/testdir` with backend running -> creates new session even if one exists
   - `codehive code` with backend down -> falls back to local mode with warning

## Acceptance Criteria

- [ ] `codehive code /some/dir` with backend running: resolves project by path, picks/creates session, sends messages through backend API
- [ ] `codehive code /some/dir` with backend down: prints warning and starts local-only session (current behavior preserved)
- [ ] `codehive code --session <uuid>` connects to the specified session
- [ ] `codehive code --new` always creates a new session
- [ ] `codehive code` with no args uses current directory and resumes the most recent session
- [ ] In backend mode, messages are sent via `POST /api/sessions/{id}/messages` and events are rendered in the TUI
- [ ] In local mode, behavior is identical to current (NativeEngine + NoOpEventBus)
- [ ] `uv run pytest tests/ -v` passes with 5+ new tests
- [ ] `uv run ruff check` passes

## Test Scenarios

### Unit: Backend detection
- Health endpoint returns 200 -> `backend_url` is set
- Health endpoint connection refused -> `backend_url` is None, warning printed

### Unit: Project resolution
- `POST /api/projects/by-path` called with absolute directory path
- Response project_id used for session lookup

### Unit: Session resolution
- Sessions list returns 3 sessions -> most recent by `created_at` is selected
- Sessions list returns empty -> new session created via POST
- `--session <uuid>` flag -> that UUID used directly, no list call
- `--new` flag -> new session created via POST, no list call

### Unit: CodeApp backend mode
- Message sent via HTTP POST, not local engine
- Events from response rendered in chat UI
- Approval flow still works (backend handles it)

## Notes

- The existing `POST /api/sessions/{id}/messages` endpoint already runs the engine and returns events -- CodeApp just needs to call it instead of running a local engine
- In backend mode, the engine runs server-side. The TUI is purely a rendering client.
- The approval callback does not work in backend mode (the backend engine does not have a TUI callback). For now, backend mode should use the backend's own approval policy. This is acceptable -- the `--auto-approve` flag can be passed to the session config.
- Future enhancement: WebSocket-based streaming for real-time deltas in backend mode (currently the POST endpoint returns all events at once, not streamed). This is tracked separately in #94c.
