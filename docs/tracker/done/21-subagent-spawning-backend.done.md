# 21: Sub-Agent Spawning Backend

## Description
Implement the backend support for sub-agent sessions. Add a `spawn_subagent` tool to the native engine, create the sub-agent lifecycle manager (spawn, monitor status, collect structured report), extend session queries to support parent-child relationships, and add an API endpoint to retrieve the sub-agent tree for a session.

## Scope
- `backend/codehive/engine/tools/spawn_subagent.py` -- Tool schema definition and spawn logic callable from the engine's tool dispatch
- `backend/codehive/core/subagent.py` -- Sub-agent lifecycle: spawn (creates child session via session CRUD), monitor (query status), collect report (validate structured format)
- `backend/codehive/core/session.py` -- Add `list_child_sessions(db, session_id)` and `get_session_tree(db, session_id)` queries
- `backend/codehive/api/routes/sessions.py` -- Add `GET /api/sessions/{session_id}/subagents` endpoint returning the sub-agent tree
- `backend/codehive/api/schemas/session.py` -- Add `SubAgentReport` and `SessionTreeRead` Pydantic schemas
- `backend/codehive/engine/native.py` -- Register `spawn_subagent` in TOOL_DEFINITIONS and add dispatch in `_execute_tool`
- `backend/tests/test_subagent.py` -- Sub-agent spawning, lifecycle, report validation, and API tests

## Structured report format
Sub-agents return this report upon completion (stored in session config or a dedicated field):
```json
{
  "status": "completed|failed|blocked",
  "summary": "string",
  "files_changed": ["list of paths"],
  "tests": {"added": 0, "passing": 0},
  "warnings": []
}
```

## Dependencies
- Depends on: #09 (engine adapter interface) -- done
- Depends on: #05 (session CRUD with parent_session_id) -- done
- Depends on: #07 (event bus for sub-agent events) -- done

## Acceptance Criteria

- [ ] `backend/codehive/core/subagent.py` exists with a `SubAgentManager` class (or equivalent module-level functions) that handles: `spawn_subagent`, `get_subagent_status`, `collect_report`
- [ ] `spawn_subagent` creates a child session via `core.session.create_session` with `parent_session_id` set to the calling session's ID, inheriting the same `project_id` and `engine`
- [ ] `spawn_subagent` accepts required parameters: `mission` (str), `role` (str), `scope` (list of file paths), and optional `config` (dict)
- [ ] `spawn_subagent` emits a `subagent.spawned` event via EventBus with data including `parent_session_id`, `child_session_id`, `mission`, and `role`
- [ ] `get_subagent_status` returns the current status of a child session (delegates to `core.session.get_session`)
- [ ] `collect_report` validates the structured report format (status must be one of completed/failed/blocked, summary is a non-empty string, files_changed is a list, tests has added/passing integer keys, warnings is a list) and returns a validated dict or raises `InvalidReportError`
- [ ] `collect_report` emits a `subagent.report` event via EventBus with the validated report data
- [ ] `backend/codehive/core/session.py` has a new `list_child_sessions(db, session_id)` function that returns all sessions where `parent_session_id == session_id`, raising `SessionNotFoundError` if the parent does not exist
- [ ] `backend/codehive/core/session.py` has a new `get_session_tree(db, session_id)` function that returns the session plus all its direct children (one level deep) as a dict with `session` and `children` keys
- [ ] `backend/codehive/engine/native.py` TOOL_DEFINITIONS includes a `spawn_subagent` tool with input_schema requiring `mission` (string), `role` (string), `scope` (array of strings), and optional `config` (object)
- [ ] `NativeEngine._execute_tool` dispatches `spawn_subagent` tool calls to `SubAgentManager.spawn_subagent` (or the module-level function), passing through the session_id as parent
- [ ] `backend/codehive/api/routes/sessions.py` has a `GET /api/sessions/{session_id}/subagents` endpoint that returns a list of child sessions with their status
- [ ] `backend/codehive/api/schemas/session.py` has a `SubAgentReport` Pydantic model matching the structured report JSON format, with validation (status enum, non-empty summary)
- [ ] `backend/codehive/api/schemas/session.py` has a `SessionTreeRead` Pydantic model with fields `session: SessionRead` and `children: list[SessionRead]`
- [ ] `uv run pytest backend/tests/test_subagent.py -v` passes with 12+ tests
- [ ] `uv run pytest backend/tests/ -v` continues to pass (no regressions)

## Test Scenarios

### Unit: SubAgentManager.spawn_subagent
- Spawn a sub-agent with valid parameters (mission, role, scope). Verify a child session is created in the DB with `parent_session_id` set to the parent, `project_id` matching the parent, status `idle`, and the mission/role/scope stored in config.
- Spawn a sub-agent with a non-existent parent session ID. Verify `SessionNotFoundError` is raised.
- Spawn a sub-agent and verify a `subagent.spawned` event is emitted via EventBus with correct parent/child IDs, mission, and role.

### Unit: SubAgentManager.collect_report
- Submit a valid report (status=completed, non-empty summary, files list, tests dict, warnings list). Verify it is accepted and returned as a validated dict.
- Submit a report with invalid status (e.g., "unknown"). Verify `InvalidReportError` is raised.
- Submit a report with empty summary. Verify `InvalidReportError` is raised.
- Submit a report missing required fields (e.g., no `tests` key). Verify `InvalidReportError` is raised.
- Submit a valid report and verify a `subagent.report` event is emitted via EventBus.

### Unit: SubAgentManager.get_subagent_status
- Create a child session, query its status via `get_subagent_status`. Verify the returned status matches the session's current status.
- Query status for a non-existent session. Verify `SessionNotFoundError` is raised.

### Unit: session.list_child_sessions
- Create a parent session with 2 child sessions. Call `list_child_sessions`. Verify both children are returned.
- Create a session with no children. Call `list_child_sessions`. Verify an empty list is returned.
- Call `list_child_sessions` with a non-existent session ID. Verify `SessionNotFoundError` is raised.

### Unit: session.get_session_tree
- Create a parent with 2 children. Call `get_session_tree`. Verify the result contains the parent session and both children.
- Create a session with no children. Call `get_session_tree`. Verify `children` is an empty list and `session` is the parent.

### Unit: spawn_subagent tool schema
- Verify `spawn_subagent` is present in `NativeEngine.tool_definitions` with correct input_schema (mission: string required, role: string required, scope: array required, config: object optional).

### Unit: spawn_subagent tool dispatch
- Mock `SubAgentManager.spawn_subagent`. Call `NativeEngine._execute_tool("spawn_subagent", {...})`. Verify SubAgentManager was called with the correct arguments and the result contains the child session ID.

### Unit: SubAgentReport schema validation
- Validate a well-formed report dict against `SubAgentReport`. Verify it passes.
- Validate a report with status not in (completed, failed, blocked). Verify Pydantic validation error.
- Validate a report with missing `summary`. Verify Pydantic validation error.

### Integration: GET /api/sessions/{session_id}/subagents
- Create a parent session with 2 child sessions via the DB. Call the endpoint. Verify 200 response with 2 sessions listed, each including id, name, status, and parent_session_id.
- Call the endpoint for a session with no children. Verify 200 with an empty list.
- Call the endpoint with a non-existent session ID. Verify 404 response.

## Log

### [SWE] 2026-03-15 10:00
- Implemented sub-agent spawning backend: lifecycle manager, session queries, API endpoint, engine tool, schemas
- Created `backend/codehive/core/subagent.py` with `SubAgentManager` class (spawn_subagent, get_subagent_status, collect_report) and `InvalidReportError`
- Created `backend/codehive/engine/tools/spawn_subagent.py` with tool schema definition
- Added `list_child_sessions` and `get_session_tree` to `backend/codehive/core/session.py`
- Added `SubAgentReport`, `SubAgentReportStatus`, `SessionTreeRead` schemas to `backend/codehive/api/schemas/session.py`
- Added `GET /api/sessions/{session_id}/subagents` endpoint to `backend/codehive/api/routes/sessions.py`
- Registered `spawn_subagent` in TOOL_DEFINITIONS and `_execute_tool` dispatch in `backend/codehive/engine/native.py`
- Files created: `backend/codehive/core/subagent.py`, `backend/codehive/engine/tools/__init__.py`, `backend/codehive/engine/tools/spawn_subagent.py`, `backend/tests/test_subagent.py`
- Files modified: `backend/codehive/core/session.py`, `backend/codehive/api/schemas/session.py`, `backend/codehive/api/routes/sessions.py`, `backend/codehive/engine/native.py`
- Tests added: 24 tests covering all test scenarios (spawn, status, report, child sessions, tree, tool schema, tool dispatch, Pydantic validation, API endpoint)
- Build results: 338 tests pass, 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-15 11:30
- Tests: 338 passed, 0 failed (24 new in test_subagent.py)
- Ruff: clean
- Format: clean
- Acceptance criteria:
  - AC1 SubAgentManager class with spawn/status/report: PASS
  - AC2 spawn creates child session with parent_session_id, inherits project_id and engine: PASS
  - AC3 spawn accepts mission, role, scope (required) and config (optional): PASS
  - AC4 spawn emits subagent.spawned event with correct data: PASS
  - AC5 get_subagent_status returns current status: PASS
  - AC6 collect_report validates structured format and raises InvalidReportError: PASS
  - AC7 collect_report emits subagent.report event: PASS
  - AC8 list_child_sessions queries children, raises SessionNotFoundError for missing parent: PASS
  - AC9 get_session_tree returns dict with session and children keys: PASS
  - AC10 TOOL_DEFINITIONS includes spawn_subagent with correct input_schema: PASS
  - AC11 _execute_tool dispatches spawn_subagent to SubAgentManager: PASS
  - AC12 GET /api/sessions/{session_id}/subagents endpoint returns child sessions: PASS
  - AC13 SubAgentReport Pydantic model with status enum and non-empty summary validation: PASS
  - AC14 SessionTreeRead Pydantic model with session and children fields: PASS
  - AC15 24 tests in test_subagent.py all pass (>= 12 required): PASS
  - AC16 Full test suite passes with no regressions (338 pass): PASS
- VERDICT: PASS

### [PM] 2026-03-15 12:15
- Reviewed diff: 8 files changed (4 new, 4 modified) -- focused on backend subagent files, ignored unrelated #14/#15 frontend changes
- New files: `backend/codehive/core/subagent.py` (175 lines), `backend/codehive/engine/tools/spawn_subagent.py` (34 lines), `backend/codehive/engine/tools/__init__.py` (empty), `backend/tests/test_subagent.py` (551 lines, 24 tests)
- Modified files: `backend/codehive/core/session.py` (+35 lines), `backend/codehive/api/schemas/session.py` (+44 lines), `backend/codehive/api/routes/sessions.py` (+14 lines), `backend/codehive/engine/native.py` (+36 lines)
- Results verified: 338 tests pass (24 new in test_subagent.py), ruff clean -- real data present in QA log
- Code quality: clean, follows existing project patterns (async/await, SQLAlchemy, Pydantic v2, pytest-asyncio fixtures). No over-engineering.
- Acceptance criteria: all 16 met
  - AC1-AC7: SubAgentManager lifecycle (spawn, status, report, events) -- verified in code
  - AC8-AC9: Session tree queries (list_child_sessions, get_session_tree) -- verified in code
  - AC10-AC11: Engine tool registration and dispatch -- verified in code
  - AC12: API endpoint GET /api/sessions/{id}/subagents with 404 handling -- verified in code
  - AC13-AC14: Pydantic schemas (SubAgentReport with enum+validator, SessionTreeRead) -- verified in code
  - AC15-AC16: Test count and regression -- verified via QA report
- Tests are meaningful: cover happy paths, error cases (nonexistent sessions, invalid reports), event emission with mocks, schema validation, and API integration (200/404 responses)
- Follow-up issues created: none needed
- VERDICT: ACCEPT
