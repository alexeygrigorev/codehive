# 79: Session Export

## Description
Export a session transcript as markdown or JSON. This is distinct from the raw event log export (#51) -- the transcript is a human-readable rendering of the session conversation: messages (user and assistant), tool calls with results, and timestamps. The backend provides a dedicated export endpoint that accepts a `format` query parameter (`markdown` or `json`). The web UI adds a download button to the session view.

## Scope
- `backend/codehive/core/transcript.py` -- Transcript builder: reads messages/events from the DB and renders them into markdown or structured JSON
- `backend/codehive/api/schemas/transcript.py` -- Pydantic schemas for transcript export responses
- `backend/codehive/api/routes/transcript.py` -- REST endpoint for session transcript export
- `backend/codehive/api/app.py` -- Register transcript router
- `web/src/api/transcript.ts` -- API client for transcript export
- `web/src/components/ExportButton.tsx` -- Download button component
- `web/src/components/ChatPanel.tsx` -- Integrate ExportButton into the chat panel header
- `backend/tests/test_transcript.py` -- Backend tests for transcript builder and endpoint
- `web/src/test/ExportButton.test.tsx` -- Frontend tests for ExportButton component

## Detailed Requirements

### 1. Transcript Builder (`core/transcript.py`)
A `TranscriptService` class that assembles a session transcript from stored data:
- Queries the `messages` table for the session, ordered by `created_at` ascending
- Queries the `events` table for `tool.call.started` and `tool.call.finished` events to include tool call context
- Builds a unified timeline merging messages and tool calls in chronological order
- Renders to **markdown** format:
  - Session header with name, status, engine, mode, created_at
  - Each message rendered as `### <Role> (<timestamp>)` followed by content
  - Tool calls rendered as fenced code blocks with tool name, input, and output
  - Clear visual separation between entries
- Renders to **JSON** format:
  - Structured object with session metadata and ordered list of transcript entries
  - Each entry has: `type` (message | tool_call), `timestamp`, `role` (for messages), `content` (for messages), `tool_name`/`input`/`output`/`is_error` (for tool calls)
- Raises `SessionNotFoundError` for non-existent sessions

### 2. Pydantic Schemas (`api/schemas/transcript.py`)
- `TranscriptEntry` -- a single transcript item: `type`, `timestamp`, `role` (optional), `content` (optional), `tool_name` (optional), `input` (optional), `output` (optional), `is_error` (optional)
- `TranscriptExportJSON` -- JSON export response: `session_id`, `session_name`, `status`, `engine`, `mode`, `created_at`, `exported_at`, `entry_count`, `entries: list[TranscriptEntry]`
- `TranscriptExportMarkdown` -- Markdown export response: `content: str` (the rendered markdown string)

### 3. REST Endpoint (`api/routes/transcript.py`)
- `GET /api/sessions/{session_id}/transcript` -- Export session transcript
  - Query param: `format` (string, default `json`, allowed values: `json`, `markdown`)
  - When `format=json`: returns `TranscriptExportJSON` with `Content-Type: application/json`
  - When `format=markdown`: returns plain text markdown with `Content-Type: text/markdown` and `Content-Disposition: attachment; filename="session-<name>.md"` header so the browser downloads it as a file
  - Returns 404 if session does not exist
  - Returns 400 if `format` is not `json` or `markdown`
  - Requires viewer-level project access (consistent with other read endpoints)

### 4. Web UI: ExportButton Component (`web/src/components/ExportButton.tsx`)
- A button (or dropdown with two options: "Export as Markdown" and "Export as JSON")
- Clicking triggers a download:
  - For markdown: fetches the endpoint with `format=markdown`, initiates browser file download
  - For JSON: fetches the endpoint with `format=json`, initiates browser file download as `.json` file
- Shows a loading/spinner state during download
- Disabled when sessionId is not available

### 5. ChatPanel Integration
- Add the ExportButton to the ChatPanel header area (top of the chat panel, alongside session info)
- Pass `sessionId` and `sessionName` (for filename) as props

### 6. Router Registration
Register the transcript router in `api/app.py`.

## Endpoints
- `GET /api/sessions/{session_id}/transcript?format=json` -- Export transcript as JSON
- `GET /api/sessions/{session_id}/transcript?format=markdown` -- Export transcript as downloadable markdown file

## Dependencies
- Depends on: #51 (persistent logs) -- DONE
- Depends on: #16 (web session chat panel) -- DONE

## Acceptance Criteria

- [ ] `TranscriptService` in `core/transcript.py` builds a transcript from messages and tool-call events for a given session
- [ ] `TranscriptService` merges messages and tool calls into a single chronological timeline
- [ ] `TranscriptService` raises `SessionNotFoundError` for non-existent sessions
- [ ] `TranscriptService.render_markdown()` produces valid markdown with session header, timestamped messages, and fenced tool-call blocks
- [ ] `TranscriptService.render_json()` returns a structured dict with session metadata and ordered entries
- [ ] `GET /api/sessions/{session_id}/transcript?format=json` returns 200 with `TranscriptExportJSON` schema
- [ ] `GET /api/sessions/{session_id}/transcript?format=markdown` returns 200 with `Content-Type: text/markdown` and `Content-Disposition` header
- [ ] `GET /api/sessions/{session_id}/transcript` (no format param) defaults to JSON
- [ ] `GET /api/sessions/{session_id}/transcript?format=invalid` returns 400
- [ ] `GET /api/sessions/{session_id}/transcript` returns 404 for non-existent session
- [ ] Transcript endpoint requires viewer-level project access
- [ ] `ExportButton` component renders in the ChatPanel with options for markdown and JSON download
- [ ] `ExportButton` triggers a browser file download when clicked
- [ ] `ExportButton` shows a loading state during the download
- [ ] Transcript router is registered in `api/app.py`
- [ ] `uv run pytest backend/tests/test_transcript.py -v` passes with 10+ tests
- [ ] Frontend tests for ExportButton pass: `npx vitest run src/test/ExportButton.test.tsx`
- [ ] All existing tests continue to pass: `uv run pytest backend/tests/ -v`

## Test Scenarios

### Unit: TranscriptService
- Build transcript for a session with only messages -- entries contain all messages in order
- Build transcript for a session with messages and tool calls -- entries interleaved chronologically
- Build transcript for a session with no messages or events -- returns empty entries list with valid metadata
- Build transcript for non-existent session -- raises SessionNotFoundError
- render_markdown() includes session name and status in header
- render_markdown() formats user messages with "User" role heading and timestamp
- render_markdown() formats assistant messages with "Assistant" role heading
- render_markdown() formats tool calls as fenced code blocks with tool name, input, output
- render_json() returns dict with session_id, session_name, entry_count, and entries list
- render_json() entry for a message has type=message, role, content, timestamp
- render_json() entry for a tool call has type=tool_call, tool_name, input, output, is_error

### Integration: REST transcript endpoint
- GET /api/sessions/{id}/transcript returns JSON transcript by default (200)
- GET /api/sessions/{id}/transcript?format=json returns TranscriptExportJSON schema
- GET /api/sessions/{id}/transcript?format=markdown returns text/markdown content type
- GET /api/sessions/{id}/transcript?format=markdown includes Content-Disposition header with session name in filename
- GET /api/sessions/{id}/transcript?format=invalid returns 400
- GET /api/sessions/{id}/transcript for non-existent session returns 404
- Transcript endpoint enforces viewer-level access (returns 403 for unauthorized user)

### Frontend: ExportButton component
- Renders a button/dropdown with markdown and JSON export options
- Clicking "Export as JSON" calls the transcript API with format=json
- Clicking "Export as Markdown" calls the transcript API with format=markdown
- Shows loading state while download is in progress
- Button is disabled when sessionId is not provided

## Log

### [SWE] 2026-03-16 16:02
- Implemented TranscriptService in core/transcript.py: queries messages and tool-call events, merges into chronological timeline, renders to markdown and JSON
- Created Pydantic schemas in api/schemas/transcript.py: TranscriptEntry, TranscriptExportJSON, TranscriptExportMarkdown
- Created REST endpoint in api/routes/transcript.py: GET /api/sessions/{id}/transcript with format query param (json/markdown), viewer-level access check, Content-Disposition for markdown downloads
- Registered transcript_router in api/app.py
- Created frontend API client in web/src/api/transcript.ts: downloadTranscript function that triggers browser file downloads
- Created ExportButton component in web/src/components/ExportButton.tsx: dropdown with Markdown/JSON options, loading state, disabled when no sessionId
- Integrated ExportButton into ChatPanel header with sessionName prop support
- Files created: backend/codehive/core/transcript.py, backend/codehive/api/schemas/transcript.py, backend/codehive/api/routes/transcript.py, web/src/api/transcript.ts, web/src/components/ExportButton.tsx, backend/tests/test_transcript.py, web/src/test/ExportButton.test.tsx
- Files modified: backend/codehive/api/app.py, web/src/components/ChatPanel.tsx
- Tests added: 19 backend tests (4 build, 5 markdown render, 3 JSON render, 7 REST endpoint), 7 frontend tests
- Build results: 19 backend tests pass, 7 frontend tests pass, 6 existing ChatPanel tests pass, ruff clean on new files
- Known limitations: none

### [QA] 2026-03-16 16:12
- Backend tests: 19 passed, 0 failed (test_transcript.py)
- Frontend tests: 7 passed, 0 failed (ExportButton.test.tsx)
- Existing tests: 1501 passed (1477 pre-existing + 24 new across issues), 0 failed, 6 ChatPanel tests pass
- Ruff check: clean (all 4 new backend files)
- Ruff format: clean (all 4 new backend files)
- Acceptance criteria:
  1. TranscriptService in core/transcript.py builds transcript from messages and tool-call events: PASS
  2. TranscriptService merges messages and tool calls into single chronological timeline: PASS
  3. TranscriptService raises SessionNotFoundError for non-existent sessions: PASS
  4. TranscriptService.render_markdown() produces valid markdown with session header, timestamped messages, fenced tool-call blocks: PASS
  5. TranscriptService.render_json() returns structured dict with session metadata and ordered entries: PASS
  6. GET /api/sessions/{id}/transcript?format=json returns 200 with TranscriptExportJSON schema: PASS
  7. GET /api/sessions/{id}/transcript?format=markdown returns 200 with Content-Type text/markdown and Content-Disposition header: PASS
  8. GET /api/sessions/{id}/transcript (no format param) defaults to JSON: PASS
  9. GET /api/sessions/{id}/transcript?format=invalid returns 400: PASS
  10. GET /api/sessions/{id}/transcript returns 404 for non-existent session: PASS
  11. Transcript endpoint requires viewer-level project access: PASS (test confirms 403 for unauthorized)
  12. ExportButton component renders in ChatPanel with markdown and JSON download options: PASS
  13. ExportButton triggers browser file download when clicked: PASS (via downloadTranscript mock verification)
  14. ExportButton shows loading state during download: PASS
  15. Transcript router registered in api/app.py: PASS
  16. uv run pytest backend/tests/test_transcript.py -v passes with 10+ tests: PASS (19 tests)
  17. Frontend tests for ExportButton pass: PASS (7 tests)
  18. All existing tests continue to pass: PASS (1477 pre-existing tests, 0 failures)
- VERDICT: PASS

### [PM] 2026-03-16 16:15
- Reviewed diff: 9 files changed (7 new, 2 modified)
- Results verified: real data present -- 19 backend tests pass (independently confirmed), 7 frontend tests pass (independently confirmed), ruff clean
- Code review:
  - TranscriptService cleanly separates DB queries, timeline merging, and rendering
  - Proper tool-call pairing via call_id with handling of unmatched started events
  - REST endpoint validates format, checks session existence, enforces viewer-level access before rendering
  - Content-Disposition header uses sanitized session name for markdown downloads
  - Frontend ExportButton uses dropdown pattern with click-outside handling, loading state, disabled when no sessionId
  - ChatPanel integration adds ExportButton in a header bar with sessionName prop
  - Tests are meaningful: unit tests for builder/render logic, integration tests for all HTTP status codes (200/400/403/404), frontend tests for UI states and API call verification
- Acceptance criteria: all 17 met
  1. TranscriptService builds transcript from messages and tool-call events: MET
  2. Merges messages and tool calls into chronological timeline: MET
  3. Raises SessionNotFoundError for non-existent sessions: MET
  4. render_markdown() produces valid markdown with header, timestamps, fenced blocks: MET
  5. render_json() returns structured dict with metadata and entries: MET
  6. GET ?format=json returns 200 with TranscriptExportJSON: MET
  7. GET ?format=markdown returns text/markdown + Content-Disposition: MET
  8. Default format is JSON: MET
  9. ?format=invalid returns 400: MET
  10. Non-existent session returns 404: MET
  11. Viewer-level access required (403 tested): MET
  12. ExportButton in ChatPanel with markdown/JSON options: MET
  13. ExportButton triggers browser download: MET
  14. ExportButton shows loading state: MET
  15. Transcript router registered in app.py: MET
  16. 19 backend tests pass (>10 required): MET
  17. 7 frontend tests pass: MET
- Follow-up issues created: none needed
- VERDICT: ACCEPT
