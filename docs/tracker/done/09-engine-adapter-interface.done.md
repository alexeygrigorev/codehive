# 09: Engine Adapter Interface

## Description
Define the engine adapter protocol and implement the native engine using the Anthropic SDK.

## Scope
- `backend/codehive/engine/__init__.py` -- Package init, re-exports
- `backend/codehive/engine/base.py` -- EngineAdapter Protocol (create_session, send_message, start_task, pause, resume, approve_action, reject_action, get_diff)
- `backend/codehive/engine/native.py` -- Native engine: Anthropic SDK conversation loop with tool use
- `backend/tests/test_engine.py` -- Engine tests (with mocked LLM responses)

## Native engine behavior
- Uses Anthropic SDK (Claude) as the LLM
- Defines tools: edit_file, read_file, run_shell, git_commit, search_files (using execution layer from #08)
- Runs conversation loop: user message -> LLM response -> tool calls -> tool results -> LLM response -> ...
- Emits events via the event bus (#07) for every message and tool call
- Respects session state machine (pause, resume)

## Dependencies
- Depends on: #07 (event bus) -- done, #08 (execution layer) -- done

## Acceptance Criteria

- [ ] `backend/codehive/engine/base.py` defines an `EngineAdapter` Protocol class with all 8 methods: `create_session`, `send_message`, `start_task`, `pause`, `resume`, `approve_action`, `reject_action`, `get_diff`
- [ ] Each Protocol method has type annotations (params and return type) and a docstring describing its purpose
- [ ] `send_message` returns `AsyncIterator[dict]` (event dicts) to support streaming
- [ ] `backend/codehive/engine/native.py` implements `NativeEngine` that satisfies the `EngineAdapter` protocol
- [ ] `NativeEngine.__init__` accepts dependencies: Anthropic client, EventBus, and execution layer components (FileOps, ShellRunner, GitOps, DiffService)
- [ ] `NativeEngine` defines tool schemas for: `edit_file`, `read_file`, `run_shell`, `git_commit`, `search_files` -- each tool delegates to the corresponding execution layer class from #08
- [ ] The conversation loop in `send_message` handles the full cycle: send user message to Anthropic API -> receive response -> if response contains tool_use blocks, execute tools via execution layer -> send tool_results back -> repeat until the model produces a final text response (no more tool calls)
- [ ] Every message exchange and tool call emits events via EventBus: at minimum `message.created`, `tool.call.started`, `tool.call.finished`
- [ ] `pause` sets an internal flag that causes the conversation loop to stop processing after the current step completes
- [ ] `resume` clears the pause flag, allowing the loop to continue
- [ ] `get_diff` delegates to DiffService to return the accumulated session diff
- [ ] `start_task` retrieves a task by ID and feeds its instructions into `send_message`
- [ ] `backend/codehive/engine/__init__.py` re-exports `EngineAdapter` and `NativeEngine`
- [ ] `uv run pytest backend/tests/test_engine.py -v` passes with 10+ tests
- [ ] All Anthropic SDK calls are mocked in tests (no real API calls)
- [ ] `uv run pytest backend/tests/ -v` continues to pass (no regressions)

## Test Scenarios

### Unit: EngineAdapter Protocol
- Verify that `NativeEngine` satisfies `EngineAdapter` protocol (runtime_checkable or structural check)
- Verify a stub class missing a method does NOT satisfy the protocol

### Unit: Tool schema definitions
- Verify `NativeEngine` exposes a list of tool definitions with correct names: edit_file, read_file, run_shell, git_commit, search_files
- Verify each tool definition has the required Anthropic tool schema fields (name, description, input_schema with JSON Schema properties)

### Unit: Tool execution dispatch
- Mock FileOps.read_file, call the engine's internal tool dispatch with a read_file tool_use block, verify FileOps.read_file was called with the correct path and the result is returned
- Mock FileOps.write_file (or edit_file), call dispatch with edit_file tool_use, verify FileOps was called correctly
- Mock ShellRunner.run, call dispatch with run_shell tool_use, verify ShellRunner.run was called with the command and working directory
- Mock GitOps.commit, call dispatch with git_commit tool_use, verify GitOps.commit was called with the message
- Mock FileOps.list_files, call dispatch with search_files tool_use, verify FileOps.list_files was called with the pattern

### Unit: Conversation loop (send_message)
- Mock Anthropic client to return a simple text response (no tool use). Verify send_message yields a message.created event with the assistant text.
- Mock Anthropic client to return a tool_use response, then on the follow-up call return a text response. Verify the loop: (1) yields tool.call.started, (2) executes the tool, (3) yields tool.call.finished with the result, (4) sends tool_result back to Anthropic, (5) yields the final message.created.
- Mock Anthropic client to return two sequential tool_use blocks in a single response. Verify both tools are executed and results sent back.
- Mock Anthropic client to return a tool_use that raises an exception (e.g., FileNotFoundError). Verify the error is caught, wrapped in a tool_result error, and the loop continues.

### Unit: Event emission
- Mock EventBus.publish. Run a conversation loop with one tool call. Verify publish was called with event types: message.created (user), tool.call.started, tool.call.finished, message.created (assistant). Verify session_id is passed correctly.

### Unit: Pause / Resume
- Set the pause flag, call send_message. Verify the loop stops early (yields no events or a paused event).
- Call resume, then send_message. Verify the loop proceeds normally.

### Unit: get_diff
- Mock DiffService.get_session_changes. Call get_diff. Verify it returns the mocked diff data.

### Unit: start_task
- Mock send_message (on the engine itself). Call start_task with a task ID and mock task data. Verify send_message is called with the task instructions as the message.

## Log

### [SWE] 2026-03-15 12:00
- Implemented EngineAdapter protocol with all 8 methods (create_session, send_message, start_task, pause, resume, approve_action, reject_action, get_diff), each with full type annotations and docstrings
- Implemented NativeEngine with Anthropic SDK conversation loop, tool dispatch, event emission, pause/resume, and diff delegation
- Defined 5 tool schemas (read_file, edit_file, run_shell, git_commit, search_files) that delegate to the execution layer
- Added `anthropic` as a dependency via `uv add anthropic`
- Files created:
  - `backend/codehive/engine/__init__.py` (re-exports EngineAdapter and NativeEngine)
  - `backend/codehive/engine/base.py` (EngineAdapter Protocol, runtime_checkable)
  - `backend/codehive/engine/native.py` (NativeEngine implementation)
  - `backend/tests/test_engine.py` (22 tests covering all test scenarios)
- Tests added: 22 tests covering protocol conformance, tool schemas, tool dispatch (7 tests), conversation loop (4 tests), event emission, pause/resume, get_diff, and start_task
- Build results: 255 tests pass (22 new + 233 existing), 0 fail, ruff clean
- All Anthropic SDK calls are mocked -- no real API calls
- Known limitations: none

### [QA] 2026-03-15 12:30
- Tests: 255 passed, 0 failed (22 engine tests + 233 existing)
- Ruff: clean (0 issues)
- Ruff format: clean (47 files already formatted)
- Acceptance criteria:
  1. EngineAdapter Protocol with 8 methods in base.py: PASS
  2. Each method has type annotations and docstring: PASS
  3. send_message returns AsyncIterator[dict]: PASS
  4. NativeEngine satisfies EngineAdapter protocol: PASS
  5. NativeEngine.__init__ accepts all dependencies (client, EventBus, FileOps, ShellRunner, GitOps, DiffService): PASS
  6. 5 tool schemas (read_file, edit_file, run_shell, git_commit, search_files) delegating to execution layer: PASS
  7. Conversation loop handles full cycle (user msg -> LLM -> tool calls -> tool results -> repeat -> final text): PASS
  8. Events emitted via EventBus (message.created, tool.call.started, tool.call.finished): PASS
  9. pause sets internal flag, loop stops after current step: PASS
  10. resume clears pause flag: PASS
  11. get_diff delegates to DiffService: PASS
  12. start_task retrieves task and feeds into send_message: PASS
  13. __init__.py re-exports EngineAdapter and NativeEngine: PASS
  14. 10+ tests (22 tests pass): PASS
  15. All Anthropic SDK calls mocked: PASS
  16. No regressions (255 total pass): PASS
- VERDICT: PASS

### [PM] 2026-03-15 13:00
- Reviewed diff: 4 new files (base.py, native.py, __init__.py, test_engine.py) + 2 modified (pyproject.toml, uv.lock)
- Results verified: real data present -- 22 engine tests pass, 255 total tests pass, all mocked correctly
- Code review:
  - EngineAdapter Protocol in base.py: clean, runtime_checkable, all 8 methods with full type annotations and docstrings
  - NativeEngine in native.py: well-structured conversation loop, proper tool dispatch to execution layer, error handling wraps exceptions into tool_result errors, pause flag checked both before loop and inside loop
  - Tool schemas follow Anthropic format with name/description/input_schema/required fields
  - Event emission gated on `db is not None` which is reasonable for test flexibility
  - Tests are meaningful: protocol conformance (positive + negative), tool dispatch (7 tests exercising real execution layer), conversation loop (4 tests covering text-only, tool use, multi-tool, error), event emission with bus verification, pause/resume, get_diff delegation, start_task with both direct instructions and fetcher callback
- Acceptance criteria: all 16 met
  1. EngineAdapter Protocol with 8 methods: MET
  2. Type annotations and docstrings on all methods: MET
  3. send_message returns AsyncIterator[dict]: MET
  4. NativeEngine satisfies EngineAdapter protocol: MET
  5. NativeEngine.__init__ accepts all dependencies: MET
  6. 5 tool schemas delegating to execution layer: MET
  7. Conversation loop handles full cycle: MET
  8. Events emitted (message.created, tool.call.started, tool.call.finished): MET
  9. pause sets flag, loop stops: MET
  10. resume clears flag: MET
  11. get_diff delegates to DiffService: MET
  12. start_task feeds instructions into send_message: MET
  13. __init__.py re-exports EngineAdapter and NativeEngine: MET
  14. 22 tests pass (10+ required): MET
  15. All Anthropic SDK calls mocked: MET
  16. No regressions (255 total pass): MET
- Follow-up issues created: none needed
- VERDICT: ACCEPT
