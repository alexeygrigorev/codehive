# 51: Persistent Session Logs

## Description
Ensure all session activity is durably stored for debugging, performance analysis, and future agent training. Store agent messages, tool calls with arguments and results, file changes, terminal output, and diff history in a queryable format.

The existing `events` table (from #07) already persists raw events with `type` and `data` (JSONB). The native engine (#09) already emits `message.created`, `tool.call.started`, `tool.call.finished`, `file.changed`, and `approval.required` events through the `EventBus`. This issue adds a **structured log service** that provides a higher-level query interface over the events table: filtering by event type, time range, pagination, and a full JSON export endpoint for session replay and training data extraction.

## Scope
- `backend/codehive/core/logs.py` -- Log query service: structured querying of session events with type and time-range filters
- `backend/codehive/api/schemas/logs.py` -- Pydantic schemas for log query responses and export format
- `backend/codehive/api/routes/logs.py` -- REST endpoints for querying and exporting session logs
- `backend/codehive/engine/native.py` -- Extend to emit `file.changed` events for `edit_file` and `terminal.output` events for `run_shell` results (currently only emits generic `tool.call.finished`)
- `backend/tests/test_logs.py` -- Log query service and endpoint tests

## Detailed Requirements

### 1. Log Query Service (`core/logs.py`)
A `LogService` class that wraps the events table with structured querying:
- Query events filtered by one or more `type` values (e.g., `type=message.created`, `type=tool.call.started,tool.call.finished`)
- Query events within a time range (`after` and `before` datetime params)
- Combine type and time-range filters
- Pagination via `limit` and `offset` (consistent with existing events endpoint)
- Return total count alongside results for pagination UI
- Raise `SessionNotFoundError` for non-existent sessions (reuse from `core/events.py`)

### 2. Pydantic Schemas (`api/schemas/logs.py`)
- `LogEntry` -- response schema for a single log entry: `id`, `session_id`, `type`, `data`, `created_at`
- `LogQueryResponse` -- paginated response: `items: list[LogEntry]`, `total: int`, `limit: int`, `offset: int`
- `LogExport` -- full export format: `session_id`, `exported_at`, `event_count`, `events: list[LogEntry]`

### 3. REST Endpoints (`api/routes/logs.py`)
- `GET /api/sessions/{session_id}/logs` -- Query session logs
  - Query params: `type` (comma-separated string, optional), `after` (ISO datetime, optional), `before` (ISO datetime, optional), `limit` (int, default 50, max 200), `offset` (int, default 0)
  - Returns `LogQueryResponse` with items, total count, limit, offset
  - Returns 404 if session does not exist
- `GET /api/sessions/{session_id}/logs/export` -- Export full session log
  - Query params: `type` (comma-separated string, optional) for filtering the export
  - Returns `LogExport` with all matching events (no pagination limit)
  - Returns 404 if session does not exist

### 4. Engine Enrichment (`engine/native.py`)
Extend the native engine to emit additional structured events so logs are more useful:
- After a successful `edit_file` tool call, emit a `file.changed` event with `{"path": <path>, "action": "edit"}`
- After a `run_shell` tool call, emit a `terminal.output` event with `{"command": <cmd>, "exit_code": <code>, "stdout": <stdout_truncated>, "stderr": <stderr_truncated>}`
- These events are emitted via the existing `EventBus.publish` in addition to the existing `tool.call.finished` event

### 5. Router Registration
Register the new logs router in `api/app.py` alongside the existing events router.

## Endpoints
- `GET /api/sessions/{session_id}/logs` -- Query session logs (filter by type, time range, paginated)
- `GET /api/sessions/{session_id}/logs/export` -- Export full session log as JSON

## Dependencies
- Depends on: #07 (events table as base storage) -- DONE
- Depends on: #09 (engine adapter emitting events) -- DONE

## Acceptance Criteria

- [ ] `LogService` in `core/logs.py` queries the `events` table with type filter, time-range filter, and pagination
- [ ] `LogService.query()` returns both items and total count
- [ ] `GET /api/sessions/{session_id}/logs` returns 200 with `LogQueryResponse` schema (items, total, limit, offset)
- [ ] `GET /api/sessions/{session_id}/logs?type=message.created` returns only events of that type
- [ ] `GET /api/sessions/{session_id}/logs?type=tool.call.started,tool.call.finished` returns events matching either type
- [ ] `GET /api/sessions/{session_id}/logs?after=<ISO>&before=<ISO>` returns events within that time range
- [ ] `GET /api/sessions/{session_id}/logs` returns 404 for non-existent session
- [ ] `GET /api/sessions/{session_id}/logs/export` returns 200 with `LogExport` schema (session_id, exported_at, event_count, events)
- [ ] `GET /api/sessions/{session_id}/logs/export?type=message.created` exports only filtered events
- [ ] `GET /api/sessions/{session_id}/logs/export` returns 404 for non-existent session
- [ ] Native engine emits `file.changed` event after successful `edit_file` tool calls
- [ ] Native engine emits `terminal.output` event after `run_shell` tool calls
- [ ] New logs router is registered in `api/app.py`
- [ ] `uv run pytest backend/tests/test_logs.py -v` passes with 12+ tests
- [ ] All existing tests continue to pass: `uv run pytest backend/tests/ -v`

## Test Scenarios

### Unit: LogService query logic
- Query with no filters returns all events for a session, ordered by created_at ascending
- Query with `types=["message.created"]` returns only message events
- Query with multiple types returns the union of matching events
- Query with `after` datetime returns only events created after that time
- Query with `before` datetime returns only events created before that time
- Query with both `after` and `before` returns events in that window
- Query with `limit=2` returns at most 2 items; total reflects the full count
- Query with `offset=1, limit=2` skips the first event
- Query for non-existent session raises `SessionNotFoundError`

### Unit: Engine event enrichment
- `edit_file` tool call emits a `file.changed` event with path and action
- `run_shell` tool call emits a `terminal.output` event with command, exit_code, stdout, stderr

### Integration: REST log query endpoint
- `GET /api/sessions/{id}/logs` returns paginated log entries with correct schema
- `GET /api/sessions/{id}/logs?type=message.created` filters by type
- `GET /api/sessions/{id}/logs?type=a,b` filters by multiple types
- `GET /api/sessions/{id}/logs?after=...&before=...` filters by time range
- `GET /api/sessions/{id}/logs` for non-existent session returns 404

### Integration: REST log export endpoint
- `GET /api/sessions/{id}/logs/export` returns all events with correct export schema
- `GET /api/sessions/{id}/logs/export?type=tool.call.started` exports filtered subset
- `GET /api/sessions/{id}/logs/export` for non-existent session returns 404

## Log

### [SWE] 2026-03-15 10:15
- Implemented LogService in core/logs.py with query() and export() methods supporting type filter, time-range filter, pagination, and total count
- Created Pydantic schemas (LogEntry, LogQueryResponse, LogExport) in api/schemas/logs.py
- Created REST endpoints GET /api/sessions/{id}/logs and GET /api/sessions/{id}/logs/export in api/routes/logs.py
- Extended NativeEngine._execute_tool_direct to emit file.changed events after edit_file and terminal.output events after run_shell
- Registered logs_router in api/app.py
- Files created: backend/codehive/core/logs.py, backend/codehive/api/schemas/logs.py, backend/codehive/api/routes/logs.py, backend/tests/test_logs.py
- Files modified: backend/codehive/api/app.py, backend/codehive/engine/native.py
- Tests added: 19 tests (9 LogService unit, 2 engine enrichment, 5 REST query endpoint, 3 REST export endpoint)
- Build results: 768 tests pass, 0 fail, ruff clean
- No known limitations

### [QA] 2026-03-15 10:45
- Tests: 768 passed, 0 failed (19 in test_logs.py)
- Ruff: clean (check + format)
- Acceptance criteria:
  1. LogService queries events with type/time-range/pagination: PASS
  2. LogService.query() returns items and total count: PASS
  3. GET /logs returns 200 with LogQueryResponse schema: PASS
  4. GET /logs?type=message.created filters by single type: PASS
  5. GET /logs?type=a,b filters by multiple types: PASS
  6. GET /logs?after=&before= filters by time range: PASS
  7. GET /logs returns 404 for non-existent session: PASS
  8. GET /logs/export returns 200 with LogExport schema: PASS
  9. GET /logs/export?type= exports filtered events: PASS
  10. GET /logs/export returns 404 for non-existent session: PASS
  11. Native engine emits file.changed after edit_file: PASS
  12. Native engine emits terminal.output after run_shell: PASS
  13. Logs router registered in api/app.py: PASS
  14. test_logs.py passes with 12+ tests (19 actual): PASS
  15. All existing tests continue to pass (768 total): PASS
- VERDICT: PASS

### [PM] 2026-03-15 11:10
- Reviewed diff: 6 files changed (4 new: core/logs.py, api/schemas/logs.py, api/routes/logs.py, tests/test_logs.py; 2 modified: engine/native.py, api/app.py)
- Results verified: real data present -- 19 tests executed and passing, endpoints return correct schemas, engine emits file.changed and terminal.output events with correct payloads
- Acceptance criteria: all 15 met
  1. LogService queries with type/time-range/pagination: MET
  2. LogService.query() returns items + total: MET
  3. GET /logs returns LogQueryResponse: MET
  4. Single type filter: MET
  5. Multi-type filter: MET
  6. Time range filter: MET
  7. 404 for non-existent session: MET
  8. GET /logs/export returns LogExport: MET
  9. Export with type filter: MET
  10. Export 404 for non-existent session: MET
  11. file.changed event after edit_file: MET
  12. terminal.output event after run_shell: MET
  13. Logs router registered in app.py: MET
  14. 19 tests in test_logs.py (threshold: 12+): MET
  15. All existing tests pass: MET
- Code quality: clean, follows existing patterns (service/schema/route separation), proper error handling, stdout/stderr truncated to 10K in terminal.output events
- Follow-up issues created: none needed
- VERDICT: ACCEPT
