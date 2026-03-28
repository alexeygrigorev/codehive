# 145 -- Task creation from conversation: chat to backlog

## Problem

Currently the user creates tasks by writing markdown files or telling the orchestrator in natural language. There is no smooth way to go from "the sidebar is broken" in a chat to a well-formed task in the backlog. The orchestrator session has no tool to programmatically create tasks -- it must rely on the human to manually hit the API or write a tracker file.

## Vision

The user chats with the orchestrator session. When they describe a problem or feature request, the orchestrator calls a `create_task` tool that creates an issue and a backlog task via the existing `/api/orchestrator/add-task` endpoint logic. The task appears in the pipeline UI immediately and the orchestrator picks it up in the next batch.

## Scope

This issue adds **one new engine tool** (`create_task`) and wires it into the orchestrator mode's allowed tool set. The backend API endpoint (`POST /api/orchestrator/add-task`) and the core logic (`create_issue`, `create_task` in task_queue) already exist. This issue is about making that functionality callable from within an agent session.

**Out of scope:**
- Natural language extraction / LLM-based parsing of user messages into structured fields (the orchestrator LLM already does this naturally when deciding to call the tool)
- Web UI changes (the pipeline UI already renders backlog tasks)
- Changes to the existing `add-task` API endpoint

## Dependencies

- No blocking dependencies. The `add-task` API endpoint and the orchestrator mode infrastructure are already in place.

## User Stories

### Story: Orchestrator agent creates a task from user conversation

1. User is chatting with an orchestrator session
2. User says: "The sidebar project list does not update when I create a new project"
3. The orchestrator LLM decides this is a bug and calls the `create_task` tool with:
   - `title`: "Sidebar project list does not refresh after project creation"
   - `description`: "When a user creates a new project, the sidebar project list does not update until the page is manually refreshed."
   - `acceptance_criteria`: "- [ ] Sidebar refreshes automatically after project creation\n- [ ] No full page reload required"
4. The tool creates an issue and a task in the backlog
5. The tool returns a confirmation with the issue ID and task ID
6. The orchestrator tells the user: "Created task -- it is now in the backlog and will be picked up automatically."

### Story: Orchestrator creates a task with minimal fields

1. User says: "Add dark mode to the settings page"
2. The orchestrator calls `create_task` with just `title` and `description` (no acceptance criteria)
3. The tool succeeds and returns IDs
4. The task enters the pipeline at the grooming step, where the PM agent adds acceptance criteria

### Story: Tool rejects invalid input

1. Orchestrator calls `create_task` without a required `title` field
2. The tool returns an error result explaining that `title` is required
3. Orchestrator retries with valid input

## Technical Notes

### New file: `backend/codehive/engine/tools/create_task.py`

Define the tool schema following the same pattern as `spawn_subagent.py` and `send_to_agent.py`:

```python
CREATE_TASK_TOOL: dict[str, Any] = {
    "name": "create_task",
    "description": "Create a new task in the project backlog. ...",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", ...},
            "description": {"type": "string", ...},
            "acceptance_criteria": {"type": "string", ...},
        },
        "required": ["title"],
    },
}
```

### Wire into orchestrator mode: `backend/codehive/engine/orchestrator.py`

Add `"create_task"` to `ORCHESTRATOR_ALLOWED_TOOLS`.

### Tool execution handler

The tool handler (wherever tool calls are dispatched -- likely in the engine adapter or a shared tool executor) must:

1. Receive the `create_task` tool call with `title`, optional `description`, optional `acceptance_criteria`
2. Resolve the `project_id` from the current session context (the session knows its project)
3. Call `create_issue(db, project_id=..., title=..., description=..., acceptance_criteria=...)`
4. Find or create the orchestrator session for the project (same logic as `add_task` endpoint)
5. Call `create_task(db, session_id=..., title=..., instructions=description, pipeline_status="backlog")`
6. Return a JSON result with `issue_id`, `task_id`, `pipeline_status`

The core logic should be extracted from the existing `add_task` endpoint in `backend/codehive/api/routes/orchestrator.py` (lines 140-197) into a reusable service function, so both the API endpoint and the tool handler call the same code. Do not duplicate the logic.

### Emit an event

After creating the task, emit a `task.created` event via the EventBus so the web UI updates in real time. Check existing event patterns in `backend/codehive/core/events.py`.

## Acceptance Criteria

- [ ] A `create_task` tool schema exists at `backend/codehive/engine/tools/create_task.py` following the same dict-based pattern as `spawn_subagent.py`
- [ ] `create_task` is listed in `ORCHESTRATOR_ALLOWED_TOOLS` in `backend/codehive/engine/orchestrator.py`
- [ ] The tool handler creates both an Issue (status "open") and a Task (pipeline_status "backlog") in the database
- [ ] The tool handler resolves `project_id` from the session context -- the caller does not pass a project ID
- [ ] The `title` field is required; `description` and `acceptance_criteria` are optional
- [ ] The tool returns a JSON-serializable result containing `issue_id`, `task_id`, and `pipeline_status`
- [ ] The core "create issue + create backlog task" logic is shared between the API endpoint and the tool handler (no duplication)
- [ ] A `task.created` event is emitted after successful creation
- [ ] `uv run pytest tests/ -v` passes with all existing tests plus new tests (see test scenarios below)
- [ ] `uv run ruff check` is clean

## Test Scenarios

### Unit: Tool schema validation

- `CREATE_TASK_TOOL` has `name` equal to `"create_task"`
- `input_schema` requires `title`
- `input_schema` has optional `description` and `acceptance_criteria` properties

### Unit: Orchestrator allowed tools

- `"create_task"` is in `ORCHESTRATOR_ALLOWED_TOOLS`
- `filter_tools()` includes `create_task` when it is present in the input list

### Unit: Shared service function

- Call the shared service function with `(db, project_id, title, description, acceptance_criteria)` -- verify it creates an Issue with status "open" and a Task with pipeline_status "backlog"
- Call with only `title` (no description, no acceptance_criteria) -- verify it succeeds
- Call with a nonexistent `project_id` -- verify it raises an appropriate error

### Integration: Tool execution in session context

- Simulate a tool call with `name="create_task"` and `input={"title": "Fix bug", "description": "Details"}` in an orchestrator session context
- Verify the tool handler returns `{"issue_id": ..., "task_id": ..., "pipeline_status": "backlog"}`
- Verify the Issue and Task rows exist in the database after the call

### Integration: API endpoint still works

- `POST /api/orchestrator/add-task` with valid payload returns 201 and creates Issue + Task (regression test -- ensure refactoring to shared service did not break it)

### Unit: Event emission

- After the shared service function creates a task, verify a `task.created` event was emitted (mock the EventBus and assert it was called)

## Log

### [SWE] 2026-03-28 12:00
- Implemented create_task tool for orchestrator sessions
- Extracted shared `create_backlog_task` service function from the add-task API endpoint
- Created tool schema at `backend/codehive/engine/tools/create_task.py`
- Added `create_task` to `ORCHESTRATOR_ALLOWED_TOOLS` in orchestrator.py
- Added tool handler in `zai_engine.py` that resolves project_id from session context
- Refactored `POST /api/orchestrator/add-task` to use the shared service
- Emits `task.created` event via EventBus after successful creation
- Updated existing orchestrator tests for new tool count (6 -> 7, 10 -> 11)
- Files created: `backend/codehive/engine/tools/create_task.py`, `backend/codehive/core/backlog_service.py`, `backend/tests/test_create_task_tool.py`
- Files modified: `backend/codehive/engine/orchestrator.py`, `backend/codehive/engine/zai_engine.py`, `backend/codehive/api/routes/orchestrator.py`, `backend/tests/test_orchestrator.py`
- Tests added: 16 new tests covering schema validation, allowed tools, shared service, event emission, tool execution, and API endpoint regression
- Build results: 2362 tests pass, 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-28 13:30
- Tests: 16 passed in test_create_task_tool.py; 2362 passed, 0 failed full suite
- Ruff: clean (check + format)
- Acceptance criteria:
  1. Tool schema at `backend/codehive/engine/tools/create_task.py` following dict pattern: PASS
  2. `create_task` in `ORCHESTRATOR_ALLOWED_TOOLS`: PASS
  3. Tool handler creates Issue (status "open") + Task (pipeline_status "backlog"): PASS
  4. Tool handler resolves project_id from session context (no caller-provided project ID): PASS
  5. `title` required; `description` and `acceptance_criteria` optional: PASS
  6. Returns JSON-serializable result with issue_id, task_id, pipeline_status: PASS
  7. Shared service between API endpoint and tool handler (no duplication): PASS -- API endpoint refactored to call `create_backlog_task`
  8. `task.created` event emitted after creation: PASS
  9. All tests pass: PASS (2362 passed, 0 failed)
  10. Ruff clean: PASS
- Test coverage: 16 tests covering schema validation (4), orchestrator allowed tools (2), shared service (3), event emission (2), tool execution (3), API endpoint regression (2)
- VERDICT: PASS

### [PM] 2026-03-28 14:00
- Reviewed diff: 7 files changed for issue #145 (orchestrator.py, zai_engine.py, orchestrator routes, new create_task.py, new backlog_service.py, test_create_task_tool.py, test_orchestrator.py)
- Results verified: real data present -- 16 new tests pass, 2362 total, ruff clean per QA log
- Acceptance criteria review:
  1. Tool schema at `backend/codehive/engine/tools/create_task.py` with dict pattern: MET
  2. `create_task` in `ORCHESTRATOR_ALLOWED_TOOLS`: MET (line 34 of orchestrator.py)
  3. Tool handler creates Issue (status "open") + Task (pipeline_status "backlog"): MET (verified in backlog_service.py and tests)
  4. project_id resolved from session context, not passed by caller: MET (zai_engine.py lines 984-990)
  5. `title` required, `description` and `acceptance_criteria` optional: MET (schema and tests confirm)
  6. Returns JSON with issue_id, task_id, pipeline_status: MET (BacklogResult.to_dict())
  7. Shared service -- no duplication between API endpoint and tool handler: MET (both call `create_backlog_task`, endpoint refactored from ~50 lines to ~10)
  8. `task.created` event emitted: MET (backlog_service.py lines 106-117, tested with LocalEventBus)
  9. All tests pass: MET (2362 total)
  10. Ruff clean: MET
- Tests are meaningful: schema validation (4), orchestrator filtering (2), shared service with DB assertions on Issue/Task rows (3), event emission with real LocalEventBus (2), tool execution through engine with DB verification (3), API endpoint regression including 404 case (2)
- Code quality: clean extraction of shared service, proper error handling with typed exceptions, consistent patterns with existing tool handlers
- Follow-up issues created: none needed
- VERDICT: ACCEPT
