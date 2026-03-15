# 11: CLI Session Commands

## Description
Add CLI commands for managing projects and sessions, and for chatting interactively with a session from the terminal. The CLI acts as an HTTP client to the running codehive API server. This also requires a new `POST /api/sessions/{id}/messages` API endpoint so the CLI (and future clients) can send messages to a session and receive streamed events.

## Scope
- `backend/codehive/cli.py` -- Extend with `projects` and `sessions` subcommand groups
- `backend/codehive/api/routes/sessions.py` -- Add `POST /api/sessions/{id}/messages` endpoint
- `backend/codehive/api/schemas/session.py` -- Add `MessageSend` request schema and `MessageEvent` response schema
- `backend/tests/test_cli.py` -- CLI tests (argument parsing, output formatting, HTTP call wiring)
- `backend/tests/test_sessions.py` -- Add tests for the new messages endpoint

## Design Decisions

### CLI is an HTTP client
The CLI commands call the REST API on a running server (default `http://127.0.0.1:8000`). The `--base-url` flag (or `CODEHIVE_BASE_URL` env var) overrides the server address. This keeps the CLI stateless and consistent with the product spec ("Non-interactive command-line interface for scripting and quick operations").

### Message endpoint required
The engine's `send_message` is not currently exposed via HTTP. This issue adds `POST /api/sessions/{id}/messages` which accepts a JSON body `{"content": "..."}` and returns a JSON list of event dicts produced by the engine. Streaming (SSE/WebSocket) is out of scope for this issue -- the endpoint collects all events and returns them as a batch response. This is sufficient for CLI chat where the user sends one message and waits for the full response.

### Interactive chat is a REPL loop
`codehive sessions chat <session_id>` enters a read-eval-print loop:
1. Print prompt (`> `)
2. Read user input from stdin
3. POST to `/api/sessions/{id}/messages`
4. Print assistant messages from the response events
5. Repeat until EOF (Ctrl+D) or the user types `/quit`

### projects create needs a workspace_id
The API requires `workspace_id` when creating a project. The CLI accepts it as `--workspace <id>`. There is no "default workspace" logic in this issue.

## Commands

### `codehive projects list`
- GET `/api/projects`
- Output: table with columns `ID | Name | Path | Created`
- If no projects exist, print "No projects found."

### `codehive projects create <name> --workspace <workspace_id> [--path <path>] [--description <desc>]`
- POST `/api/projects` with `{workspace_id, name, path, description}`
- Output: "Created project <name> (<id>)"

### `codehive sessions list --project <project_id>`
- GET `/api/projects/{project_id}/sessions`
- Output: table with columns `ID | Name | Engine | Mode | Status | Created`
- If no sessions exist, print "No sessions found."

### `codehive sessions create <project_id> --name <name> [--engine <engine>] [--mode <mode>]`
- POST `/api/projects/{project_id}/sessions` with `{name, engine, mode}`
- `--engine` defaults to `"native"`
- `--mode` defaults to `"execution"`
- Output: "Created session <name> (<id>)"

### `codehive sessions status <session_id>`
- GET `/api/sessions/{session_id}`
- Output: formatted session details (id, name, project_id, engine, mode, status, created_at)

### `codehive sessions chat <session_id>`
- Verifies session exists via GET `/api/sessions/{session_id}`, prints session name and status
- Enters REPL loop:
  - Reads input from stdin (prompt: `> `)
  - Sends message via POST `/api/sessions/{session_id}/messages`
  - Prints assistant response text from returned events
  - Exits on EOF or `/quit`

## API Endpoint

### `POST /api/sessions/{session_id}/messages`

**Request body** (`MessageSend`):
- `content`: str (required) -- the user message

**Response** (200): JSON list of event dicts from the engine. Each event has at minimum:
- `type`: str (e.g. `message.created`, `tool.call.started`, `tool.call.finished`)
- `data`: dict (event-specific payload)

The endpoint:
1. Validates the session exists (404 if not)
2. Instantiates the engine (NativeEngine) with required dependencies
3. Calls `engine.send_message(session_id, content)`
4. Collects all yielded events into a list
5. Returns the list as JSON

For this issue the engine dependencies (Anthropic client, EventBus, FileOps, etc.) are wired up with defaults from config. The Anthropic API key must be configured. If the key is missing, return 503 with "Engine not configured".

## Dependencies
- Depends on: #09 (engine adapter) -- DONE
- Depends on: #04 (project CRUD API) -- DONE
- Depends on: #05 (session CRUD API) -- DONE

## Acceptance Criteria

- [ ] `uv run pytest backend/tests/test_cli.py -v` passes with 12+ tests
- [ ] `uv run pytest backend/tests/ -v` passes with no regressions
- [ ] `codehive projects list` calls GET `/api/projects` and prints a formatted table (or "No projects found." if empty)
- [ ] `codehive projects create myproject --workspace <uuid>` calls POST `/api/projects` and prints the created project ID
- [ ] `codehive projects create` with missing `--workspace` flag prints an error and exits non-zero
- [ ] `codehive sessions list --project <uuid>` calls GET `/api/projects/{id}/sessions` and prints a formatted table
- [ ] `codehive sessions list` without `--project` prints an error and exits non-zero
- [ ] `codehive sessions create <project_id> --name mysession` calls POST `/api/projects/{id}/sessions` with engine="native" and mode="execution" defaults
- [ ] `codehive sessions create <project_id> --name mysession --engine claude_code --mode brainstorm` passes the specified engine and mode
- [ ] `codehive sessions status <session_id>` calls GET `/api/sessions/{id}` and prints session details (id, name, status, engine, mode)
- [ ] `codehive sessions chat <session_id>` verifies the session exists, enters a REPL, sends messages via POST `/api/sessions/{id}/messages`, and prints the assistant response
- [ ] `codehive sessions chat` exits cleanly on EOF (Ctrl+D) and on `/quit`
- [ ] POST `/api/sessions/{id}/messages` with valid body returns 200 and a list of event dicts
- [ ] POST `/api/sessions/{id}/messages` with non-existent session returns 404
- [ ] POST `/api/sessions/{id}/messages` with missing `content` field returns 422
- [ ] All CLI commands accept `--base-url` flag to override the server address (default `http://127.0.0.1:8000`)
- [ ] The `--base-url` flag is also configurable via `CODEHIVE_BASE_URL` env var
- [ ] CLI uses `httpx` (sync client) for HTTP calls -- add as a dependency if not present
- [ ] CLI error handling: connection refused prints "Cannot connect to server at <url>. Is it running?" and exits non-zero
- [ ] CLI error handling: API 404 responses print the error detail and exit non-zero

## Test Scenarios

### Unit: CLI argument parsing
- `codehive projects list` parses correctly with command="projects", action="list"
- `codehive projects create myproject --workspace <uuid>` parses name, workspace_id
- `codehive projects create myproject` (missing --workspace) results in argparse error
- `codehive sessions list --project <uuid>` parses project_id
- `codehive sessions list` (missing --project) results in argparse error
- `codehive sessions create <uuid> --name mysession` parses project_id, name, defaults engine="native", mode="execution"
- `codehive sessions create <uuid> --name mysession --engine claude_code --mode brainstorm` parses all flags
- `codehive sessions status <uuid>` parses session_id
- `codehive sessions chat <uuid>` parses session_id
- `--base-url http://example.com` overrides the default base URL

### Unit: CLI output formatting
- `projects list` with API returning 2 projects prints a table with headers and 2 rows
- `projects list` with API returning empty list prints "No projects found."
- `sessions list` with API returning 3 sessions prints a table with headers and 3 rows
- `sessions status` prints formatted session details
- `projects create` success prints "Created project <name> (<id>)"
- `sessions create` success prints "Created session <name> (<id>)"

### Unit: CLI error handling
- Connection refused (httpx.ConnectError) prints user-friendly message and exits non-zero
- API returns 404 -> CLI prints error detail and exits non-zero
- API returns 422 -> CLI prints validation error and exits non-zero

### Unit: Chat REPL
- Mock HTTP client: send one message, receive events with assistant text, verify output printed
- EOF (empty readline) exits the loop cleanly
- `/quit` input exits the loop cleanly

### Integration: Messages API endpoint
- POST `/api/sessions/{id}/messages` with `{"content": "hello"}` returns 200 and a list of events (engine mocked to return known events)
- POST `/api/sessions/{id}/messages` with non-existent session_id returns 404
- POST `/api/sessions/{id}/messages` with empty body returns 422
- POST `/api/sessions/{id}/messages` when engine raises an exception returns 500 with error detail

### Integration: CLI end-to-end (with test server)
- Start test client, create a workspace and project via API, run `codehive projects list` and verify the project appears in output
- Create a session via API, run `codehive sessions status <id>` and verify output contains session name and status

## Log

### [SWE] 2026-03-15 12:00
- Implemented CLI commands: `projects list`, `projects create`, `sessions list`, `sessions create`, `sessions status`, `sessions chat`
- CLI acts as HTTP client using httpx (moved from dev to runtime dependency)
- Added `--base-url` flag and `CODEHIVE_BASE_URL` env var support for all commands
- Added `POST /api/sessions/{id}/messages` API endpoint that instantiates NativeEngine, sends message, collects events, returns batch JSON
- Added `MessageSend` and `MessageEvent` Pydantic schemas
- Extracted `_build_engine()` helper in sessions routes for testability
- Chat REPL reads from stdin, sends messages, prints assistant responses, exits on EOF or `/quit`
- Error handling: connection refused, 404, 422, and generic HTTP errors all produce user-friendly messages
- Files modified: `backend/codehive/cli.py`, `backend/codehive/api/routes/sessions.py`, `backend/codehive/api/schemas/session.py`, `backend/pyproject.toml`
- Files created: `backend/tests/test_cli.py`
- Tests added: 25 tests covering argument parsing (10), output formatting (4), error handling (3), chat REPL (3), base URL flag (2), messages endpoint integration (4: 404, 422, success with mocked engine, engine error 500)
- Build results: 314 tests pass, 0 fail, ruff clean

### [QA] 2026-03-15 12:45
- Tests: 314 passed, 0 failed (25 in test_cli.py)
- Ruff check: clean
- Ruff format: clean
- Acceptance criteria:
  1. pytest test_cli.py passes with 12+ tests: PASS (25 tests)
  2. Full test suite passes with no regressions: PASS (314 total)
  3. `projects list` calls GET /api/projects, prints table or empty message: PASS
  4. `projects create` calls POST /api/projects, prints created ID: PASS
  5. `projects create` missing --workspace exits non-zero: PASS
  6. `sessions list --project` calls GET, prints table: PASS
  7. `sessions list` missing --project exits non-zero: PASS
  8. `sessions create` with defaults engine=native, mode=execution: PASS
  9. `sessions create` with custom --engine and --mode: PASS
  10. `sessions status` prints session details: PASS
  11. `sessions chat` REPL sends messages, prints response: PASS
  12. `sessions chat` exits on EOF and /quit: PASS
  13. POST /api/sessions/{id}/messages returns 200 with events: PASS
  14. POST messages with non-existent session returns 404: PASS
  15. POST messages with missing content returns 422: PASS
  16. All CLI commands accept --base-url flag: PASS
  17. --base-url configurable via CODEHIVE_BASE_URL env var: PASS
  18. CLI uses httpx (sync client) as dependency: PASS
  19. Connection refused prints friendly message, exits non-zero: PASS
  20. API 404 responses print error detail, exit non-zero: PASS
- VERDICT: PASS

### [PM] 2026-03-15 13:15
- Reviewed diff: 5 files changed (cli.py, sessions routes, session schemas, app.py, pyproject.toml) + 1 new file (test_cli.py)
- Results verified: real data present -- 25 tests pass with full coverage of all 6 CLI subcommands, messages endpoint, REPL, error handling
- Code quality: clean, well-structured, follows project patterns. Helper functions extracted for testability. Error handling is thorough.
- Acceptance criteria: all 20 met
  1. 25 tests in test_cli.py (req 12+): MET
  2. Full suite 314 pass, no regressions: MET
  3. projects list with table/empty output: MET
  4. projects create prints ID: MET
  5. projects create missing --workspace errors: MET
  6. sessions list --project prints table: MET
  7. sessions list missing --project errors: MET
  8. sessions create defaults engine=native, mode=execution: MET
  9. sessions create custom engine/mode: MET
  10. sessions status prints details: MET
  11. sessions chat REPL sends/receives: MET
  12. chat exits on EOF and /quit: MET
  13. POST messages returns 200 with events: MET
  14. POST messages 404 for missing session: MET
  15. POST messages 422 for missing content: MET
  16. --base-url flag accepted: MET
  17. CODEHIVE_BASE_URL env var: MET
  18. httpx as dependency: MET
  19. Connection refused friendly message: MET
  20. API 404 error detail printed: MET
- Follow-up issues created: none needed
- VERDICT: ACCEPT
