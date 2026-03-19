# Issue #130b: Subsession result collection -- get structured results from child sessions

## Problem

After #130a, an orchestrator can spawn subsessions with different engines and send an initial message. But the orchestrator needs richer tools to manage subsessions over their lifecycle:

1. **Get results**: The `query_agent` tool returns status and recent events, but not a structured completion report (files changed, test results, summary). The `collect_report` method on SubAgentManager exists but is never called by any tool.
2. **Wait for completion**: There is no tool that blocks until a subsession finishes and returns its final result. The orchestrator has to poll with `query_agent`.
3. **List my subsessions**: The orchestrator has no tool to list its own child sessions. It must remember session IDs from spawn calls.

## Dependencies

- #130a must be done first (engine selection and initial message execution)

## Scope

### In scope

1. **`get_subsession_result` tool** -- returns the structured report (status, summary, files_changed, tests, warnings) if the subsession has completed, or current status if still running.
2. **`list_subsessions` tool** -- returns a list of the calling session's child sessions with their IDs, names, engines, and statuses.
3. **Auto-collect report on subsession completion** -- when a subsession's status transitions to `completed`/`failed`/`blocked`, emit a `subagent.report` event on the parent's event stream.

### Out of scope

- Web UI changes (issue #130c)
- Blocking/waiting for subsession completion within a tool call (complex; better to let the orchestrator poll or react to events)
- Parallel subsession fan-out tool

## User Stories

### Story: Orchestrator checks on a running subsession

1. Orchestrator previously spawned a claude_code subsession (session ID returned from spawn)
2. Orchestrator calls `get_subsession_result` with the child session ID
3. The tool returns: `{status: "executing", summary: null, progress: "3 tool calls completed"}`
4. Orchestrator decides to wait and check again later

### Story: Orchestrator collects results from a completed subsession

1. Orchestrator spawned a subsession that has finished its work
2. Orchestrator calls `get_subsession_result` with the child session ID
3. The tool returns: `{status: "completed", summary: "Added health check endpoint", files_changed: ["api/health.py"], tests: {added: 2, passing: 2}, warnings: []}`
4. Orchestrator uses this to decide next steps

### Story: Orchestrator lists all its subsessions to check progress

1. Orchestrator has spawned 3 subsessions for different tasks
2. Orchestrator calls `list_subsessions` (no parameters needed -- it lists the caller's children)
3. The tool returns a list: `[{id: "...", name: "subagent-swe", engine: "claude_code", status: "completed"}, {id: "...", name: "subagent-tester", engine: "native", status: "executing"}, ...]`
4. Orchestrator sees which are done and which are still running

### Story: Orchestrator tries to get results for a session that is not its child

1. Orchestrator calls `get_subsession_result` with a session ID that belongs to a different parent
2. The tool returns an error: "Session {id} is not a child of the current session"

## Acceptance Criteria

- [ ] `get_subsession_result` tool schema exists in `engine/tools/` and is registered in ZaiEngine's TOOL_DEFINITIONS
- [ ] `get_subsession_result` returns structured report for completed subsessions (status, summary, files_changed, tests, warnings)
- [ ] `get_subsession_result` returns current status with event count for in-progress subsessions
- [ ] `get_subsession_result` rejects requests for sessions that are not children of the caller
- [ ] `list_subsessions` tool schema exists in `engine/tools/` and is registered in ZaiEngine's TOOL_DEFINITIONS
- [ ] `list_subsessions` returns all child sessions of the calling session with id, name, engine, status
- [ ] Both tools are available in orchestrator mode (added to ORCHESTRATOR_ALLOWED_TOOLS)
- [ ] `cd backend && uv run pytest tests/ -v` passes with 8+ new tests
- [ ] `cd backend && uv run ruff check` is clean

## Test Scenarios

### Unit: get_subsession_result

- Completed subsession with valid report: returns full structured report
- Running subsession: returns status "executing" with event count
- Failed subsession: returns status "failed" with error info from last event
- Session not a child of caller: returns error
- Nonexistent session ID: returns error

### Unit: list_subsessions

- Session with 3 children: returns list of 3 with correct fields
- Session with 0 children: returns empty list
- Returns correct engine field per child (different engines)

### Integration: Tool dispatch in ZaiEngine

- `_execute_tool_direct("get_subsession_result", ...)` calls the right manager method
- `_execute_tool_direct("list_subsessions", ...)` calls `list_child_sessions`
- Both tools are in ORCHESTRATOR_ALLOWED_TOOLS

## Files to Modify

- `backend/codehive/engine/tools/` -- add `get_subsession_result.py` and `list_subsessions.py`
- `backend/codehive/core/subagent.py` -- add `get_result()` method that combines status check + report collection
- `backend/codehive/engine/zai_engine.py` -- register new tools, add dispatch cases
- `backend/codehive/engine/orchestrator.py` -- add new tools to ORCHESTRATOR_ALLOWED_TOOLS
- `backend/tests/test_subagent.py` -- add tests for new functionality

## Notes

- The `collect_report` method already validates the report format. For `get_subsession_result`, we need to either (a) pull a stored report from the DB/events, or (b) synthesize one from the session's last events. Option (b) is simpler for now -- look at the last `message.created` event with role `assistant` as the summary.
- `list_subsessions` reuses the existing `list_child_sessions()` from `core/session.py`.
