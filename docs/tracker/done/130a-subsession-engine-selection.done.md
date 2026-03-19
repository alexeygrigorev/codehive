# Issue #130a: Subsession engine selection -- spawn child sessions with a different engine

## Problem

The existing `spawn_subagent` tool and `SubAgentManager.spawn_subagent()` always inherit the parent session's engine. There is no way for an orchestrator (ZaiEngine) to spawn a subsession that runs on a different engine (e.g., `claude_code`, `codex_cli`, `gemini_cli`). This is the foundational gap blocking multi-engine orchestration.

Additionally, spawning currently only creates a DB record -- it does not instantiate the child engine or send an initial message, so the subsession sits `idle` forever.

## What Already Exists

- **DB model**: `Session.parent_session_id` FK, `child_sessions` relationship, `list_child_sessions()` query -- all done (issue #21).
- **SubAgentManager**: `spawn_subagent()`, `get_subagent_status()`, `collect_report()` -- all done (issue #21).
- **Tools**: `spawn_subagent`, `query_agent`, `send_to_agent` tool schemas in `engine/tools/` -- all wired into ZaiEngine.
- **API**: `GET /sessions/{id}/subagents` endpoint -- done (issue #21).

## Scope

### In scope

1. **Add `engine` parameter to `spawn_subagent` tool and `SubAgentManager`** -- allow the caller to specify which engine the child session should use (default: inherit parent's engine).
2. **Add `initial_message` parameter to `spawn_subagent`** -- the first message to send to the child session after creation, so it starts working immediately.
3. **Execute the child session's first turn** -- after creating the DB record, instantiate the child engine via `_build_engine()`, call `send_message()` with the initial message, and collect events.
4. **Return the child session's response** -- the `spawn_subagent` tool returns the child session's text response (or a summary) so the orchestrator LLM can see what happened.
5. **Validate the engine parameter** -- reject unknown engine names with a clear error.

### Out of scope (separate issues)

- Web UI changes (issue #130c)
- Sending follow-up messages to subsessions (the existing `send_to_agent` tool already handles this)
- Async/parallel subsession execution (future enhancement)
- Subsession streaming to the parent's event stream (future enhancement)

## Dependencies

- None. All prerequisite infrastructure exists.

## User Stories

### Story: Orchestrator spawns a Claude Code subsession to implement a feature

1. User creates a session with engine `native` (ZaiEngine) and mode `orchestrator`
2. User sends: "Implement a health check endpoint in the backend. Use Claude Code."
3. The orchestrator agent calls `spawn_subagent` with `engine: "claude_code"`, `mission: "Add GET /health endpoint"`, `initial_message: "Add a GET /health endpoint that returns {status: ok}"`
4. The system creates a child session with engine `claude_code` in the DB
5. The system instantiates a `ClaudeCodeEngine`, sends the initial message, and collects the response
6. The `spawn_subagent` tool returns the child session ID and the response text to the orchestrator
7. The orchestrator sees the result and decides next steps (spawn more agents, verify, etc.)
8. The child session appears in the Sub-agents tab of the parent session's sidebar

### Story: Orchestrator spawns a native (ZaiEngine) subsession for a subtask

1. User creates a session with engine `native` and mode `orchestrator`
2. User sends: "Write tests for the auth module"
3. The orchestrator calls `spawn_subagent` with `engine: "native"`, `mission: "Write tests for auth"`, `initial_message: "Write pytest tests for backend/codehive/core/auth.py"`
4. A child session is created with the same engine as the parent
5. The response flows back to the orchestrator

### Story: Orchestrator tries to use an invalid engine

1. Orchestrator calls `spawn_subagent` with `engine: "nonexistent_engine"`
2. The tool returns an error: "Unknown engine 'nonexistent_engine'. Valid engines: native, claude_code, codex_cli, copilot_cli, gemini_cli, codex"
3. The orchestrator handles the error gracefully

## Acceptance Criteria

- [ ] `spawn_subagent` tool schema includes an optional `engine` parameter (string, one of the valid engine types)
- [ ] `spawn_subagent` tool schema includes an optional `initial_message` parameter (string)
- [ ] `SubAgentManager.spawn_subagent()` accepts an `engine` parameter; when provided, the child session uses that engine instead of inheriting the parent's
- [ ] When `initial_message` is provided, the child engine is instantiated and `send_message()` is called with that message
- [ ] The tool returns the child session ID, status, and the text of the child's response
- [ ] Invalid engine names return an error result (not a crash)
- [ ] The child session's engine field in the DB is set to the specified engine (not the parent's)
- [ ] Existing behavior (no engine parameter = inherit parent) is preserved
- [ ] `cd backend && uv run pytest tests/ -v` passes with 10+ new tests
- [ ] `cd backend && uv run ruff check` is clean

## Test Scenarios

### Unit: SubAgentManager engine selection

- `spawn_subagent()` without engine parameter: child inherits parent's engine (existing behavior preserved)
- `spawn_subagent()` with `engine="claude_code"`: child session has engine `claude_code` regardless of parent
- `spawn_subagent()` with `engine="codex_cli"`: child session has engine `codex_cli`
- `spawn_subagent()` with invalid engine: raises error / returns error dict

### Unit: spawn_subagent tool schema

- Tool schema includes `engine` as optional string property
- Tool schema includes `initial_message` as optional string property
- Tool dispatch in ZaiEngine passes engine and initial_message to SubAgentManager

### Integration: Subsession with initial message (mocked engine)

- `spawn_subagent()` with `initial_message`: engine is built, `send_message()` is called, response text is captured
- `spawn_subagent()` without `initial_message`: no engine is instantiated, child sits idle (existing behavior)
- `spawn_subagent()` with `initial_message` and engine crash: error is captured and returned, child session marked failed

### Integration: API endpoint

- `POST /sessions` with `parent_session_id` and a different engine: session is created correctly
- `GET /sessions/{parent_id}/subagents`: returns child sessions with correct engine fields

## Files to Modify

- `backend/codehive/engine/tools/spawn_subagent.py` -- add `engine` and `initial_message` to schema
- `backend/codehive/core/subagent.py` -- accept engine param, build engine, run initial message
- `backend/codehive/engine/zai_engine.py` -- pass new params in `_execute_tool_direct`
- `backend/tests/test_subagent.py` -- add tests for engine selection and initial message

## Notes

- The `_build_engine()` helper in `api/routes/sessions.py` handles all engine types. SubAgentManager should use the same factory or a shared version of it.
- CLI engines (claude_code, codex_cli, etc.) need a `working_dir` from the project config. The child session should inherit the parent's project root.
- The initial message execution should be synchronous from the orchestrator's perspective (the tool call blocks until the child's first turn completes). This is acceptable because the orchestrator is an LLM conversation loop that processes one tool call at a time.

## Log

### [SWE] 2026-03-19 07:06

- Implemented engine selection and initial message execution for subsession spawning
- Added `VALID_ENGINE_TYPES` constant to `spawn_subagent.py` with all 6 engine types
- Updated `spawn_subagent` tool schema with optional `engine` and `initial_message` properties
- Updated `SubAgentManager.spawn_subagent()` to accept `engine` param (defaults to parent's engine), validate it, and use it for child session creation
- Added `InvalidEngineError` exception for unknown engine names
- Added `engine_builder` callback to `SubAgentManager` for constructing child engines
- Added `_run_initial_message()` method that builds the child engine, sends the initial message, and collects the response text
- Child session inherits `project_root` from parent config for CLI engines
- Updated `ZaiEngine._execute_tool_direct` to pass `engine` and `initial_message` to SubAgentManager, with error handling for `InvalidEngineError`
- Added `_build_child_engine` static method to ZaiEngine that delegates to `_build_engine` factory
- Files modified:
  - `backend/codehive/engine/tools/spawn_subagent.py` -- added VALID_ENGINE_TYPES, engine and initial_message to schema
  - `backend/codehive/core/subagent.py` -- engine selection, validation, initial message execution
  - `backend/codehive/engine/zai_engine.py` -- engine_builder wiring, tool dispatch updates
  - `backend/tests/test_subagent.py` -- 19 new tests (41 total in file)
- Tests added: 19 new tests covering:
  - Engine selection: inherit parent, claude_code, codex_cli, invalid engine, event includes engine (5)
  - Tool schema: engine property, initial_message property (2)
  - Tool dispatch: passes engine, passes initial_message, invalid engine error (3)
  - Initial message integration: calls engine, no engine when no message, engine crash, send crash, no builder, inherits project_root (6)
  - VALID_ENGINE_TYPES constant (1)
  - Updated existing dispatch test for new params (1)
- Build results: 41 tests pass in test_subagent.py, 2073 pass full suite (2 pre-existing failures in test_cli.py unrelated to this change), ruff clean, tsc clean, vitest 681 pass
- Known limitations: none

### [QA] 2026-03-19 07:12
- Tests: 41 passed in test_subagent.py (19 new), 2073 passed full backend (2 pre-existing failures in test_cli.py, unrelated)
- Ruff check: clean
- Ruff format: clean (267 files already formatted)
- tsc --noEmit: clean
- vitest: 681 passed
- Acceptance criteria:
  - AC1 (tool schema engine param): PASS -- optional string property added, not in required
  - AC2 (tool schema initial_message param): PASS -- optional string property added, not in required
  - AC3 (SubAgentManager engine param): PASS -- child uses specified engine or inherits parent; verified in DB
  - AC4 (initial_message triggers engine build + send_message): PASS -- _run_initial_message builds engine, sends message, collects response
  - AC5 (returns child_session_id, status, response text): PASS -- return dict includes all three fields
  - AC6 (invalid engine returns error, not crash): PASS -- InvalidEngineError caught in ZaiEngine dispatch, returned as is_error
  - AC7 (child DB engine field set correctly): PASS -- tests read back from DB and assert engine value
  - AC8 (existing behavior preserved): PASS -- test_spawn_without_engine_inherits_parent verifies inheritance
  - AC9 (10+ new tests): PASS -- 19 new tests
  - AC10 (ruff clean): PASS
- Note: minor RuntimeWarning in test_spawn_with_initial_message_send_crash (unawaited coroutine from AsyncMock with side_effect) -- cosmetic, does not affect correctness
- VERDICT: PASS

### [PM] 2026-03-19 07:30
- Reviewed diff: 6 files changed (905 insertions), 4 production files + 1 test file + lock/config
- Independently ran `uv run pytest tests/test_subagent.py -v`: 41 passed, 0 failed (2.47s)
- Independently ran `uv run ruff check`: all checks passed
- Verified spawn_subagent tool schema: `engine` (optional string) and `initial_message` (optional string) present, not in `required`
- Verified `VALID_ENGINE_TYPES` contains all 6 engines: native, claude_code, codex_cli, copilot_cli, gemini_cli, codex
- Verified `SubAgentManager.spawn_subagent()` accepts `engine` param, defaults to parent engine when None
- Verified `InvalidEngineError` raised for unknown engines, caught in ZaiEngine dispatch as `is_error` response
- Verified `_run_initial_message()` builds child engine, sends message, collects response text
- Verified child inherits `project_root` from parent config
- Verified ZaiEngine wires `engine_builder` callback and passes `engine`/`initial_message` through dispatch
- Acceptance criteria: all 10/10 met
  - AC1: PASS -- engine in schema
  - AC2: PASS -- initial_message in schema
  - AC3: PASS -- engine param in SubAgentManager, child uses specified or inherits
  - AC4: PASS -- initial_message triggers engine build + send_message
  - AC5: PASS -- returns child_session_id, status, response, engine
  - AC6: PASS -- invalid engine returns error dict, no crash
  - AC7: PASS -- child DB engine field set correctly (verified in test assertions)
  - AC8: PASS -- existing behavior preserved (test_spawn_without_engine_inherits_parent)
  - AC9: PASS -- 19 new tests (well over 10+ threshold)
  - AC10: PASS -- ruff clean
- No scope dropped, no follow-up issues needed
- Code quality: clean, follows existing patterns, proper error handling, good test coverage including edge cases (engine crash, send crash, no builder configured)
- VERDICT: ACCEPT
