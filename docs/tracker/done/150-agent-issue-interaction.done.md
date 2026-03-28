# 150 -- Agent issue interaction: read_issue and write_issue_log tools

## Problem

Agents running inside sessions (PM, SWE, QA, OnCall) currently have no way to programmatically read issue details or append log entries to issues. The orchestrator manages issues via API routes, but agents operating through the engine tool system cannot interact with issues during their conversation loop. This means agents cannot:

- Read the acceptance criteria of the issue they are working on
- Append structured log entries (findings, test results, verdicts) to the issue

The `create_task` tool already exists (issue #145) and covers issue creation. This issue adds the two missing read/write tools.

## Scope

**In scope:**
- `read_issue` tool: fetch issue details (title, description, acceptance_criteria, status, log entries)
- `write_issue_log` tool: append a log entry with agent_role and content to an issue
- Both tools registered in TOOL_DEFINITIONS and wired through `_execute_tool_direct`
- Both tools available to all agent roles and in orchestrator mode
- Unit and integration tests

**Out of scope (already done or separate):**
- `create_task` tool (done in #145)
- Web UI changes (the web UI already renders issue log entries via `TaskDetailPanel.tsx` and the `GET /api/issues/{id}/logs` endpoint -- new log entries written by tools will appear automatically)

## Dependencies

- #145 (`create_task` tool) -- DONE (merged)

## User Stories

### Story: SWE agent reads the issue spec before implementing

1. Orchestrator spawns a SWE sub-agent session linked to an issue
2. SWE agent calls `read_issue` with the issue ID
3. Tool returns JSON containing `title`, `description`, `acceptance_criteria`, `status`, and `log_entries`
4. SWE agent uses the acceptance criteria to guide implementation
5. The returned `log_entries` array shows previous agent activity (e.g., PM grooming notes)

### Story: QA agent writes a test report to the issue log

1. QA agent finishes running tests for an issue
2. QA agent calls `write_issue_log` with `issue_id`, `agent_role: "qa"`, and `content` containing the test results
3. Tool returns the created log entry with `id`, `agent_role`, `content`, `created_at`
4. The log entry is visible in the web UI's TaskDetailPanel under "Issue Log Entries"
5. Subsequent calls to `read_issue` include this new log entry in the `log_entries` array

### Story: PM agent reads issue and writes acceptance verdict

1. PM agent calls `read_issue` to review the issue and all log entries
2. PM sees SWE's implementation log and QA's test report in `log_entries`
3. PM calls `write_issue_log` with `agent_role: "pm"` and content containing the acceptance verdict
4. The verdict appears in the issue log timeline

### Story: Tool returns clear error for nonexistent issue

1. Agent calls `read_issue` with a UUID that does not exist
2. Tool returns `{"content": "Issue <uuid> not found", "is_error": true}`
3. Agent calls `write_issue_log` with a nonexistent issue ID
4. Tool returns `{"content": "Issue <uuid> not found", "is_error": true}`

## Acceptance Criteria

- [ ] `read_issue` tool schema defined in `backend/codehive/engine/tools/read_issue.py` with `issue_id` (string, required) as input
- [ ] `read_issue` returns JSON with fields: `id`, `title`, `description`, `acceptance_criteria`, `status`, `priority`, `assigned_agent`, `created_at`, `updated_at`, `log_entries` (array of `{id, agent_role, content, created_at}`)
- [ ] `write_issue_log` tool schema defined in `backend/codehive/engine/tools/write_issue_log.py` with `issue_id` (string, required), `agent_role` (string, required), `content` (string, required)
- [ ] `write_issue_log` returns JSON with the created log entry: `id`, `issue_id`, `agent_role`, `content`, `created_at`
- [ ] Both tools are added to `TOOL_DEFINITIONS` list in `zai_engine.py`
- [ ] Both tools have handler branches in `_execute_tool_direct` in `zai_engine.py`
- [ ] Both tools are added to `ORCHESTRATOR_ALLOWED_TOOLS` set in `orchestrator.py`
- [ ] Both tools require `session_id` and `db` (return error if None, like `create_task`)
- [ ] `read_issue` returns `is_error: true` when issue ID does not exist
- [ ] `write_issue_log` returns `is_error: true` when issue ID does not exist
- [ ] `uv run pytest tests/ -v` passes with 10+ new tests covering both tools
- [ ] `uv run ruff check` is clean

## Technical Notes

### Existing patterns to follow

- **Tool schema file:** Follow `backend/codehive/engine/tools/create_task.py` pattern -- a single `dict[str, Any]` constant named `READ_ISSUE_TOOL` / `WRITE_ISSUE_LOG_TOOL`.
- **Tool registration:** Import in `zai_engine.py` and append to `TOOL_DEFINITIONS` list.
- **Tool dispatch:** Add `elif tool_name == "read_issue":` and `elif tool_name == "write_issue_log":` branches in `_execute_tool_direct`, following the `create_task` pattern (check session_id/db, resolve project context if needed, call core functions).
- **Core functions:** `get_issue()` and `create_issue_log_entry()` already exist in `backend/codehive/core/issues.py` with the exact signatures needed. `get_issue()` eagerly loads `sessions` and `logs` relationships. Use these directly -- do not duplicate logic.
- **UUID handling:** Tool input is a string; parse with `uuid.UUID(tool_input["issue_id"])`. Follow the pattern from `query_agent` handler.
- **Orchestrator tools:** Add both tool names to the `ORCHESTRATOR_ALLOWED_TOOLS` set in `orchestrator.py`. These are read-only and write-log-only (not destructive), so they should be allowed for orchestrator mode.
- **Serialization:** Use `json.dumps()` on the result dict. For datetime fields, convert to ISO 8601 strings. For UUID fields, convert to strings.

### DB model reference

The `Issue` model has fields: `id`, `project_id`, `title`, `description`, `acceptance_criteria`, `assigned_agent`, `status`, `priority`, `github_issue_id`, `created_at`, `updated_at`. Relationships: `sessions`, `logs`.

The `IssueLogEntry` model has fields: `id`, `issue_id`, `agent_role`, `content`, `created_at`.

### read_issue serialization

```python
{
    "id": str(issue.id),
    "title": issue.title,
    "description": issue.description,
    "acceptance_criteria": issue.acceptance_criteria,
    "status": issue.status,
    "priority": issue.priority,
    "assigned_agent": issue.assigned_agent,
    "created_at": issue.created_at.isoformat(),
    "updated_at": issue.updated_at.isoformat(),
    "log_entries": [
        {
            "id": str(log.id),
            "agent_role": log.agent_role,
            "content": log.content,
            "created_at": log.created_at.isoformat(),
        }
        for log in issue.logs
    ],
}
```

## Test Scenarios

### Unit: Tool schema validation

- `read_issue` tool has name "read_issue" and requires "issue_id" string parameter
- `write_issue_log` tool has name "write_issue_log" and requires "issue_id", "agent_role", "content" string parameters
- Both schemas have correct `input_schema` structure

### Unit: Orchestrator allowed tools

- "read_issue" is in `ORCHESTRATOR_ALLOWED_TOOLS`
- "write_issue_log" is in `ORCHESTRATOR_ALLOWED_TOOLS`
- `filter_tools()` includes both tools when they are in `TOOL_DEFINITIONS`

### Unit: Tool dispatch via _execute_tool_direct

- `read_issue` with valid issue_id returns JSON with all expected fields
- `read_issue` with nonexistent issue_id returns `is_error: true`
- `read_issue` with no session/db returns `is_error: true` with "requires an active session"
- `read_issue` includes log entries in the response
- `write_issue_log` with valid issue_id creates a log entry and returns it as JSON
- `write_issue_log` with nonexistent issue_id returns `is_error: true`
- `write_issue_log` with no session/db returns `is_error: true` with "requires an active session"

### Integration: Round-trip read after write

- Create an issue, call `write_issue_log` to add a log entry, then call `read_issue` -- the log entry appears in the `log_entries` array
- Write multiple log entries with different agent_roles, read issue -- all entries present in chronological order

## Log

### [SWE] 2026-03-28 12:00
- Implemented `read_issue` tool schema in `backend/codehive/engine/tools/read_issue.py`
- Implemented `write_issue_log` tool schema in `backend/codehive/engine/tools/write_issue_log.py`
- Registered both tools in `TOOL_DEFINITIONS` in `zai_engine.py`
- Added dispatch handlers for both tools in `_execute_tool_direct` in `zai_engine.py`
- Added both tools to `ORCHESTRATOR_ALLOWED_TOOLS` in `orchestrator.py`
- Updated existing orchestrator tests (tool count 7->9, full set 11->13) in `test_orchestrator.py`
- Files modified: `backend/codehive/engine/tools/read_issue.py` (new), `backend/codehive/engine/tools/write_issue_log.py` (new), `backend/codehive/engine/zai_engine.py`, `backend/codehive/engine/orchestrator.py`, `backend/tests/test_issue_tools.py` (new), `backend/tests/test_orchestrator.py`
- Tests added: 22 new tests covering schema validation, tool registration, orchestrator allowed tools, dispatch (valid/not-found/no-session), log entries in read, and round-trip integration
- Build results: 40 tests pass (orchestrator + issue tools), ruff clean
- Known limitations: none

### [QA] 2026-03-28 12:30
- Tests: 22 passed in test_issue_tools.py, 2408 passed full suite (3 skipped), 0 failed
- Ruff check: clean
- Ruff format: FAIL -- tests/test_issue_tools.py needs reformatting (line wrap on test_read_issue_not_found signature)
- Acceptance criteria:
  - read_issue tool schema in read_issue.py with issue_id required: PASS
  - read_issue returns JSON with all required fields (id, title, description, acceptance_criteria, status, priority, assigned_agent, created_at, updated_at, log_entries): PASS
  - write_issue_log tool schema in write_issue_log.py with issue_id, agent_role, content required: PASS
  - write_issue_log returns JSON with created log entry (id, issue_id, agent_role, content, created_at): PASS
  - Both tools added to TOOL_DEFINITIONS in zai_engine.py: PASS
  - Both tools have handler branches in _execute_tool_direct in zai_engine.py: PASS
  - Both tools added to ORCHESTRATOR_ALLOWED_TOOLS in orchestrator.py: PASS
  - Both tools require session_id and db (return error if None): PASS
  - read_issue returns is_error true for nonexistent issue: PASS
  - write_issue_log returns is_error true for nonexistent issue: PASS
  - 10+ new tests covering both tools: PASS (22 tests)
  - ruff check clean: PASS
- VERDICT: FAIL
- Issue: `ruff format --check` fails on `backend/tests/test_issue_tools.py` -- the function signature on line 250 needs reformatting. Run `cd backend && uv run ruff format tests/test_issue_tools.py` to fix.

### [PM] 2026-03-28 13:00
- Reviewed diff: 6 files changed (2 new tool schemas, zai_engine.py handlers, orchestrator.py allowed tools, test_issue_tools.py new, test_orchestrator.py updated)
- Results verified: real data present -- 22/22 tests pass, ruff check clean, ruff format clean
- Acceptance criteria: all 12 met
  - read_issue schema in read_issue.py with issue_id required: MET
  - read_issue returns JSON with all specified fields including log_entries: MET
  - write_issue_log schema in write_issue_log.py with issue_id, agent_role, content required: MET
  - write_issue_log returns JSON with created log entry fields: MET
  - Both tools in TOOL_DEFINITIONS: MET
  - Both tools have handler branches in _execute_tool_direct: MET
  - Both tools in ORCHESTRATOR_ALLOWED_TOOLS: MET
  - Both tools require session_id and db: MET
  - read_issue returns is_error true for nonexistent issue: MET
  - write_issue_log returns is_error true for nonexistent issue: MET
  - 10+ new tests: MET (22 tests)
  - ruff check clean: MET
- Follow-up issues created: none
- VERDICT: ACCEPT
