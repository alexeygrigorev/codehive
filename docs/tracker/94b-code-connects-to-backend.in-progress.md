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

- [ ] `codehive code --help` shows `--session <uuid>` and `--new` flags
- [ ] `_code()` probes `GET /api/system/health` on the configured base URL (from `--base-url`, `CODEHIVE_BASE_URL`, or default `http://127.0.0.1:7433`) before launching CodeApp
- [ ] When health probe succeeds: `_code()` calls `POST /api/projects/by-path` with the absolute directory path and passes `backend_url`, `project_id`, `session_id` to CodeApp
- [ ] When health probe fails (connection refused / timeout): `_code()` prints "Backend not available, starting local-only session" to stderr and launches CodeApp in local mode (current behavior)
- [ ] Session resolution (backend available, no flags): calls `GET /api/projects/{project_id}/sessions`, picks session with most recent `created_at`, or creates a new one if list is empty
- [ ] `--session <uuid>` flag: uses that UUID directly, skips session list/create
- [ ] `--new` flag: calls `POST /api/projects/{project_id}/sessions` to create a new session, skips session list
- [ ] CodeApp constructor accepts new optional params: `backend_url: str | None = None`, `session_id: uuid.UUID | None = None`, `project_id: uuid.UUID | None = None`
- [ ] In backend mode (`backend_url` is set), `_run_agent()` sends `POST /api/sessions/{session_id}/messages {"content": "..."}` via `httpx.AsyncClient` and iterates over the returned JSON event list, rendering each event in the TUI
- [ ] In backend mode, `_init_engine()` does NOT create a local NativeEngine, AsyncAnthropic client, or any execution services (FileOps, ShellRunner, etc.)
- [ ] In local mode (`backend_url` is None), behavior is identical to current: NativeEngine + `_NoOpEventBus`, requires `api_key`
- [ ] `Ctrl+N` (new session) works in backend mode: calls the create-session API and updates `_session_id`
- [ ] `cd backend && uv run pytest tests/ -v` passes with 7+ new tests covering all scenarios below
- [ ] `cd backend && uv run ruff check` passes

## Test Scenarios

### Unit: Backend detection (`test_code_backend_detection.py`)
- Mock `GET /api/system/health` returning 200 -> `_code()` enters backend mode (calls `POST /api/projects/by-path`)
- Mock `GET /api/system/health` raising `httpx.ConnectError` -> `_code()` enters local mode, warning printed to stderr
- Mock `GET /api/system/health` returning 500 -> `_code()` enters local mode (any non-200 = fallback)
- Mock `GET /api/system/health` timing out -> `_code()` enters local mode

### Unit: Project resolution (`test_code_project_resolution.py`)
- `POST /api/projects/by-path` called with `{"path": "/absolute/project/dir"}`
- Response `{"id": "<uuid>", "name": "project-dir", ...}` -> `project_id` extracted and used for session lookup
- Error response from by-path (e.g. 500) -> falls back to local mode with warning

### Unit: Session resolution (`test_code_session_resolution.py`)
- Sessions list returns 3 sessions with different `created_at` -> most recent is selected
- Sessions list returns empty `[]` -> new session created via `POST /api/projects/{project_id}/sessions` with `{"name": "code-session", "engine": "native", "mode": "execution"}`
- `--session <uuid>` flag present -> that UUID used directly, no GET or POST calls to sessions API
- `--new` flag present -> `POST /api/projects/{project_id}/sessions` called, no GET call
- `--session` and `--new` are mutually exclusive (argparse error)

### Unit: CodeApp backend mode (`test_code_app_backend_mode.py`)
- CodeApp with `backend_url` set: `_init_engine()` does NOT instantiate NativeEngine
- CodeApp with `backend_url` set: `_run_agent("hello")` sends `POST /api/sessions/{session_id}/messages` with `{"content": "hello"}`
- Events returned from POST (e.g. `[{"type": "message.created", "role": "assistant", "content": "Hi"}]`) are rendered as assistant messages in the UI
- Tool call events (`tool.call.started`, `tool.call.finished`) from backend response are rendered
- HTTP error from messages endpoint (e.g. 500) -> error shown in chat UI, not a crash

### Unit: CodeApp local mode (`test_code_app_local_mode.py`)
- CodeApp with `backend_url=None` initializes NativeEngine as before (regression test)

## Implementation Notes

- Auth is not needed for the endpoints used by `codehive code`: `POST /api/projects/by-path` and `POST /api/sessions/{id}/messages` have no auth dependency. Session create/list endpoints use `get_current_user`, but with `auth_enabled=False` (default), this returns `AnonymousUser` automatically -- no token needed.
- Use `httpx.AsyncClient` for backend HTTP calls in CodeApp (it's already a dependency). The existing `_code()` function uses sync `httpx.Client` for health/project/session resolution before launching the Textual app.
- The existing `POST /api/sessions/{id}/messages` endpoint returns events as a JSON list (not streamed). Backend mode will therefore render all events at once after the response returns. Real-time streaming via WebSocket is a future enhancement (#94c).
- In backend mode, the approval callback does not apply -- the backend engine uses its own approval policy. The `--auto-approve` flag should be stored in the session config dict so the backend engine can read it.
- The `_code()` function should use a short timeout (2-3 seconds) for the health probe to avoid blocking the user when the backend is down.
- `--session` and `--new` should be added as a mutually exclusive argparse group.

## Log

### [SWE] 2026-03-18 10:00
- Implemented backend detection, project/session resolution in cli.py
- Added --session and --new mutually exclusive flags to `codehive code`
- Added _probe_backend() with 3s timeout for health check
- Added _resolve_project_and_session() for project-by-path + session resolution
- Updated _code() to probe backend, resolve project/session, and pass to CodeApp
- Updated CodeApp constructor with backend_url, session_id, project_id params
- Updated _init_engine() to skip NativeEngine in backend mode
- Added _send_backend_message() async generator for backend mode
- Updated _run_agent() to use backend or local engine
- Updated action_new_session() for backend mode (creates session via API)
- Files modified: backend/codehive/cli.py, backend/codehive/clients/terminal/code_app.py
- Files created: backend/tests/test_code_backend_detection.py, backend/tests/test_code_project_resolution.py, backend/tests/test_code_session_resolution.py, backend/tests/test_code_app_backend_mode.py
- Tests added: 25 new tests across 4 test files
- Build results: 1697 tests pass, 0 fail, ruff clean on changed files
- Known limitations: pre-existing ruff errors in codehive/api/app.py (not touched by this issue)
