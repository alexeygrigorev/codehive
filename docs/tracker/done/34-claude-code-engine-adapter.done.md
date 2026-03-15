# 34: Claude Code Engine Adapter

## Description
Implement the EngineAdapter interface for Claude Code, connecting the CLI wrapper (#33) to the session system. Sessions can be created with `engine: claude_code` and use the same UI, task management, and diff viewer as native sessions.

The `ClaudeCodeProcess` and `ClaudeCodeParser` already exist in `backend/codehive/engine/claude_code.py` and `claude_code_parser.py` respectively. This issue wraps them in a `ClaudeCodeEngine` class that satisfies the `EngineAdapter` protocol defined in `backend/codehive/engine/base.py`, and wires it into the session creation and message-sending routes.

## Scope

### New: `ClaudeCodeEngine` class
- `backend/codehive/engine/claude_code_engine.py` -- New file implementing the full `EngineAdapter` protocol using `ClaudeCodeProcess` and `ClaudeCodeParser`. Must implement all 8 protocol methods:
  - `create_session(session_id)` -- Spawn a `ClaudeCodeProcess`, store in internal session map
  - `send_message(session_id, message)` -- Send message via process stdin, read stdout lines, parse with `ClaudeCodeParser`, yield codehive event dicts as `AsyncIterator[dict]`
  - `start_task(session_id, task_id)` -- Fetch task instructions and delegate to `send_message`
  - `pause(session_id)` -- Set pause flag (stop reading stdout loop at next opportunity)
  - `resume(session_id)` -- Clear pause flag, resume reading
  - `approve_action(session_id, action_id)` -- Forward approval to Claude Code process (or store locally if Claude Code handles it via its own permission flow)
  - `reject_action(session_id, action_id)` -- Forward rejection
  - `get_diff(session_id)` -- Use `DiffService` or delegate to `git diff` in project working dir

### Modify: Route-level engine selection
- `backend/codehive/api/routes/sessions.py` -- Extend `_build_engine()` to check `session.engine` field and return either `NativeEngine` or `ClaudeCodeEngine`. Currently it always builds a `NativeEngine`.
- The `send_message_endpoint` must work identically for both engines.

### New: Tests
- `backend/tests/test_claude_code_engine.py` -- Engine adapter unit and integration tests

## Dependencies
- Depends on: #33 (Claude Code CLI wrapper) -- DONE
- Depends on: #09 (engine adapter interface) -- DONE

## Acceptance Criteria

- [ ] `ClaudeCodeEngine` class exists in `backend/codehive/engine/claude_code_engine.py` and satisfies the `EngineAdapter` protocol (verified by `isinstance(engine, EngineAdapter)` returning `True`)
- [ ] `ClaudeCodeEngine` implements all 8 protocol methods: `create_session`, `send_message`, `start_task`, `pause`, `resume`, `approve_action`, `reject_action`, `get_diff`
- [ ] `send_message` returns an `AsyncIterator[dict]` that yields codehive event dicts (same format as `NativeEngine`: each dict has at least `type` and `session_id` keys)
- [ ] `create_session` spawns a `ClaudeCodeProcess` with the correct working directory (from session config `project_root`)
- [ ] `pause` stops the stdout reading loop; `resume` allows it to continue
- [ ] `get_diff` returns a `dict[str, str]` mapping file paths to unified diff text
- [ ] `_build_engine()` in `sessions.py` returns `ClaudeCodeEngine` when `session.engine == "claude_code"` and `NativeEngine` when `session.engine == "native"`
- [ ] Creating a session via `POST /api/projects/{id}/sessions` with `engine: "claude_code"` persists correctly (existing schema already accepts any string for engine)
- [ ] `POST /api/sessions/{id}/messages` works for both `native` and `claude_code` sessions without the caller needing to know which engine is in use
- [ ] Process lifecycle: `ClaudeCodeEngine` cleans up (stops) the `ClaudeCodeProcess` when the session ends or errors out
- [ ] `uv run pytest backend/tests/test_claude_code_engine.py -v` passes with 10+ tests

## Test Scenarios

### Unit: ClaudeCodeEngine protocol compliance
- Instantiate `ClaudeCodeEngine`, verify `isinstance(engine, EngineAdapter)` is True
- Verify all 8 protocol method names exist and are callable

### Unit: create_session
- Call `create_session(session_id)`, verify a `ClaudeCodeProcess` is spawned (mock subprocess)
- Call `create_session` with config containing `project_root`, verify it is passed as `working_dir`
- Call `create_session` twice with same session_id, verify it handles gracefully (either raises or replaces)

### Unit: send_message
- Mock `ClaudeCodeProcess` stdout to emit stream-json lines (assistant, tool_use, tool_result), verify `send_message` yields the correct codehive events in order
- Verify each yielded event dict contains `type` and `session_id` keys
- Verify `send_message` on a non-existent session_id raises or auto-creates
- Mock process crash mid-stream, verify `session.failed` event is yielded

### Unit: pause / resume
- Create session, call `pause`, verify session is marked paused
- Create session, call `pause` then `resume`, verify session is no longer paused
- While paused, `send_message` should yield a `session.paused` event and stop (or block until resumed)

### Unit: approve_action / reject_action
- Create session, add a pending action, call `approve_action`, verify it resolves
- Create session, add a pending action, call `reject_action`, verify it resolves

### Unit: get_diff
- Create session, mock `DiffService` to return known diffs, verify `get_diff` returns the same dict
- Create session with no changes, verify `get_diff` returns empty dict

### Unit: start_task
- Create session, call `start_task` with task instructions, verify it delegates to `send_message`

### Integration: Engine selection in routes
- Mock `_build_engine` or use test client: create session with `engine: "claude_code"`, call messages endpoint, verify `ClaudeCodeEngine` is used (not `NativeEngine`)
- Create session with `engine: "native"`, verify `NativeEngine` is used (regression)
- Create session with `engine: "unknown_engine"`, verify appropriate error (400 or 503)

### Integration: Process + Parser + Engine pipeline
- Feed mocked stream-json through `ClaudeCodeProcess` stdout, verify `ClaudeCodeEngine.send_message` yields correct codehive events end-to-end (reuses existing test pattern from `test_claude_code_wrapper.py`)

## Log

### [SWE] 2026-03-15 12:00
- Implemented `ClaudeCodeEngine` class satisfying the `EngineAdapter` protocol, wrapping `ClaudeCodeProcess` and `ClaudeCodeParser`
- All 8 protocol methods implemented: create_session, send_message, start_task, pause, resume, approve_action, reject_action, get_diff
- Extended `_build_engine()` in sessions.py to accept `engine_type` parameter and route to `ClaudeCodeEngine` for "claude_code" or `NativeEngine` for "native", returning 400 for unknown types
- Updated `send_message_endpoint` to pass `session.engine` to `_build_engine`
- Added `ClaudeCodeEngine` export to `engine/__init__.py`
- Fixed two existing tests in test_cli.py whose mock_build_engine functions needed the new `engine_type` parameter
- Files modified: backend/codehive/engine/claude_code_engine.py (new), backend/codehive/engine/__init__.py, backend/codehive/api/routes/sessions.py, backend/tests/test_claude_code_engine.py (new), backend/tests/test_cli.py
- Tests added: 22 tests covering protocol compliance, create_session, send_message, pause/resume, approve/reject, get_diff, start_task, cleanup, engine selection routing, and full pipeline integration
- Build results: 544 tests pass, 0 fail, ruff clean (on modified files)
- Known limitations: approve_action/reject_action store state locally rather than forwarding to Claude Code CLI (Claude Code handles permissions via its own flow)

### [QA] 2026-03-15 13:45
- Tests: 22 passed, 0 failed (test_claude_code_engine.py); 544 passed full suite
- Ruff check: clean
- Ruff format: clean
- Acceptance criteria:
  1. ClaudeCodeEngine exists and satisfies EngineAdapter protocol: PASS
  2. All 8 protocol methods implemented: PASS
  3. send_message yields AsyncIterator[dict] with type and session_id keys: PASS
  4. create_session spawns ClaudeCodeProcess with correct working_dir: PASS
  5. pause stops stdout reading; resume allows continue: PASS
  6. get_diff returns dict[str, str]: PASS
  7. _build_engine() routes by engine type (claude_code/native/unknown->400): PASS
  8. POST session with engine: "claude_code" persists correctly: PASS
  9. POST messages works for both engines transparently: PASS
  10. Process lifecycle cleanup on session end/error: PASS
  11. 10+ tests pass (22 tests): PASS
- Note: diff includes unrelated changes (deletion of issues 14/46 .todo.md files, app.py adding issue routes) -- these are orchestration side effects, not part of issue 34 scope
- VERDICT: PASS

### [PM] 2026-03-15 14:30
- Reviewed diff: 5 files changed (2 new, 3 modified) plus 2 unrelated .todo.md deletions (issues 14, 46) that should not be committed with this issue
- Code review:
  - ClaudeCodeEngine (184 lines) is clean, well-documented, follows existing patterns from NativeEngine
  - All 8 EngineAdapter protocol methods match base.py signatures (extra **kwargs on send_message/start_task are compatible)
  - _build_engine() refactored cleanly into engine_type dispatch with lazy imports per branch
  - test_cli.py mock_build_engine signatures updated correctly for new parameter
  - 22 tests are substantive: mock at subprocess level, test real parsing pipeline, cover edge cases (crash, pause, duplicate session, nonexistent session)
- Results verified: 22/22 tests pass (confirmed by running pytest directly), isinstance protocol check confirmed
- Acceptance criteria: all 11 met
  1. ClaudeCodeEngine exists, isinstance(engine, EngineAdapter) == True: MET
  2. All 8 protocol methods implemented: MET
  3. send_message yields AsyncIterator[dict] with type + session_id keys: MET
  4. create_session spawns ClaudeCodeProcess with working_dir from config: MET
  5. pause/resume controls stdout reading loop: MET
  6. get_diff returns dict[str, str]: MET
  7. _build_engine() routes claude_code/native/unknown correctly: MET
  8. POST session with engine "claude_code" persists: MET (schema passes through)
  9. POST messages works transparently for both engines: MET
  10. Process lifecycle cleanup on end/error: MET
  11. 22 tests pass (requirement was 10+): MET
- Follow-up issues created: none needed
- Note to committer: exclude the unrelated deletions of docs/tracker/14-react-app-scaffolding.todo.md and docs/tracker/46-issue-tracker-api.todo.md from the commit for this issue
- VERDICT: ACCEPT
