# 21: Sub-Agent Spawning Backend

## Description
Implement the backend support for sub-agent sessions. Add a `spawn_subagent` tool to the engine, enforce the parent-child session relationship, and define the structured report format that sub-agents return upon completion.

## Scope
- `backend/codehive/engine/tools/spawn_subagent.py` -- Tool that creates a child session with a mission, role, and scope
- `backend/codehive/core/subagent.py` -- Sub-agent lifecycle: spawn, monitor, collect report
- `backend/codehive/core/session.py` -- Extend to support parent_session_id queries and sub-agent listing
- `backend/codehive/api/routes/sessions.py` -- Extend to return sub-agent tree for a session
- `backend/tests/test_subagent.py` -- Sub-agent spawning and report tests

## Structured report format
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
- Depends on: #09 (engine adapter interface)
- Depends on: #05 (session CRUD with parent_session_id)
- Depends on: #07 (event bus for sub-agent events)
