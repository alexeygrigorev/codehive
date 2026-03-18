# Issue #121: Refactor Claude Code engine to fire-and-forget subagent model

## Problem

The current `ClaudeCodeEngine` and `ClaudeCodeProcess` use a long-running interactive process model (`--input-format stream-json` with stdin pipes). This does not match how the `claude` CLI works best:

1. **No `--resume` support** -- if the process crashes, the entire session context is lost.
2. **`_build_engine()` creates a new engine per request** -- it calls `create_session()` which spawns a new subprocess every time, so conversation history is never preserved between messages.
3. **`--input-format stream-json` is fragile** -- the process hangs waiting for stdin, and there is no clean way to detect when a turn is complete vs. when the process is idle.
4. **No auto-retry on crash** -- a single crash loses everything.

The `telegram-writing-assistant` project demonstrates the correct pattern: fire-and-forget subagent per message using `-p`, with `--resume` for conversation continuity and `--output-format stream-json` for streaming events.

## Approach

Replace the long-running interactive process model with fire-and-forget subprocess invocations, following the `telegram-writing-assistant` pattern:

### Current model (broken):
```
ClaudeCodeProcess: long-running subprocess with stdin/stdout pipes
  - claude --print --output-format stream-json --input-format stream-json
  - Send messages via stdin JSON
  - Read responses from stdout
  - One process per session, kept alive between messages
```

### New model (fire-and-forget):
```
Per-message subprocess:
  - First message:  claude -p "{message}" --output-format stream-json --verbose
  - Subsequent:     claude -p "{message}" --output-format stream-json --verbose --resume {session_id}
  - Capture session_id from system.init event
  - Stream JSON events from stdout to SSE
  - Process exits when turn is complete
  - Auto-retry with --resume on non-zero exit code (up to 3 attempts)
```

## Scope

### In scope:
- Rewrite `ClaudeCodeProcess` to use fire-and-forget `-p` flag instead of long-running pipes
- Rewrite `ClaudeCodeEngine` to manage claude session IDs (from `system.init` events) and use `--resume`
- Add auto-retry logic (like `SessionRetrier` from telegram-writing-assistant)
- Update `ClaudeCodeParser` to handle `system.init` events (extract `session_id`)
- Existing SSE streaming endpoint (`/messages/stream`) continues to work -- events flow from subprocess stdout through parser to SSE
- Existing tests updated to reflect the new subprocess model

### Out of scope:
- Changes to the `EngineAdapter` protocol interface (the external contract stays the same)
- Changes to the web frontend (it already consumes SSE events)
- Changes to other engines (native/codex/codex_cli)
- Tool allowlisting configuration (use defaults for now)
- Approval gates integration with Claude Code's own permission system

## Dependencies

- No blocking dependencies. Issues #33 (CLI wrapper) and #34 (engine adapter) are already done.

## Design Details

### New `ClaudeCodeProcess` behavior

The class is rewritten from a long-running process manager to a per-invocation runner:

```python
class ClaudeCodeProcess:
    """Runs a single claude -p invocation and streams events."""

    async def run(
        self,
        message: str,
        *,
        resume_session_id: str | None = None,
        working_dir: str | None = None,
    ) -> AsyncIterator[str]:
        """Spawn claude -p, yield stdout lines, return when process exits."""
        # Build command:
        #   claude -p "{message}" --output-format stream-json --verbose
        #   + --resume {session_id} if resuming
        # Yield each stdout line as it arrives
        # On completion, check exit code
```

### New `ClaudeCodeEngine` state management

Instead of holding a live subprocess per session, the engine holds:

```python
class _SessionState:
    claude_session_id: str | None  # From system.init event, used for --resume
    retry_count: int               # Current retry count for auto-resume
    paused: bool
```

### `send_message` flow:

1. Build command: `claude -p "{message}" --output-format stream-json --verbose`
2. If `claude_session_id` exists in state, add `--resume {id}`
3. Spawn subprocess with `asyncio.create_subprocess_exec`
4. Read stdout line by line, parse with `ClaudeCodeParser`
5. On `system.init` event, extract and save `session_id` to state
6. Yield codehive events as they are parsed
7. On process exit:
   - Exit code 0: turn complete, return
   - Exit code non-zero: attempt auto-retry (up to 3 times with `--resume`)
   - If all retries fail: yield `session.failed` event

### `ClaudeCodeParser` updates:

Add handling for `system.init` events:
```python
if msg_type == "system" and data.get("subtype") == "init":
    return [{
        "type": "session.started",
        "session_id": sid,
        "claude_session_id": data.get("session_id", ""),
        "model": data.get("model", ""),
    }]
```

### Auto-retry on crash:

```python
MAX_RETRIES = 3

# If subprocess exits non-zero:
for attempt in range(MAX_RETRIES):
    # Re-spawn with --resume {claude_session_id}
    # Prompt: "Continue. You were interrupted."
    # If succeeds: break
    # If fails: increment, try again
# If all fail: yield session.failed
```

## User Stories

### Story: Developer sends a message via the web chat and sees Claude Code respond

1. User opens a session page for a project with engine set to `claude_code`
2. User types "Add a health check endpoint to the API" in the chat input
3. User clicks Send
4. The chat shows streaming responses: text messages, tool use indicators (reading files, editing files, running commands)
5. When Claude Code finishes its turn, the streaming stops and the chat shows the final response
6. The session status returns to `waiting_input`

### Story: Developer sends a follow-up message and Claude Code remembers context

1. User already sent one message (story above) and received a response
2. User types "Now add tests for that endpoint"
3. User clicks Send
4. Claude Code resumes the previous session (using `--resume`) and has full context of what it did before
5. The response references the endpoint it created in the previous turn

### Story: Claude Code crashes mid-task and auto-recovers

1. User sends a message
2. Claude Code starts working but crashes (non-zero exit code) partway through
3. The system automatically retries with `--resume` and a continuation prompt
4. Claude Code picks up where it left off
5. The user sees the response complete normally (possibly with a brief pause)
6. If 3 retries all fail, the user sees an error message in the chat

## E2E Test Scenarios

This issue is a backend-only refactor. There is no UI change -- the SSE streaming endpoint contract is unchanged. E2E tests are not applicable. Verification is through unit and integration tests.

## Acceptance Criteria

- [ ] `ClaudeCodeProcess` no longer uses `--input-format stream-json` or stdin pipes. It uses `claude -p "{message}" --output-format stream-json --verbose` per invocation.
- [ ] `ClaudeCodeProcess` accepts an optional `resume_session_id` parameter and adds `--resume {id}` to the command when provided.
- [ ] `ClaudeCodeEngine.send_message()` captures `session_id` from `system.init` events and stores it in session state for subsequent `--resume` calls.
- [ ] `ClaudeCodeEngine.send_message()` auto-retries on non-zero exit code, up to 3 times, using `--resume` with a continuation prompt.
- [ ] `ClaudeCodeEngine.send_message()` yields a `session.failed` event after all retries are exhausted.
- [ ] `ClaudeCodeParser` handles `system.init` events and emits a `session.started` event containing the `claude_session_id` and `model`.
- [ ] The `EngineAdapter` protocol interface is unchanged -- `ClaudeCodeEngine` still satisfies it.
- [ ] The SSE streaming endpoint (`POST /api/sessions/{id}/messages/stream`) still works with the new engine -- events flow from subprocess stdout through parser to SSE.
- [ ] `cd backend && uv run pytest tests/ -v` passes with 15+ tests covering the new engine behavior.
- [ ] `cd backend && uv run ruff check` is clean.

## Test Scenarios

### Unit: ClaudeCodeProcess (new fire-and-forget model)

- `run()` spawns `claude -p` with correct flags (no `--input-format`)
- `run()` with `resume_session_id` adds `--resume {id}` to the command
- `run()` yields stdout lines as they arrive
- `run()` returns cleanly on exit code 0
- `run()` raises or returns error info on non-zero exit code
- Working directory is passed correctly to subprocess

### Unit: ClaudeCodeEngine send_message

- First message: no `--resume`, captures `session_id` from `system.init` event
- Second message: uses `--resume {session_id}` from stored state
- Auto-retry on crash: retries up to 3 times with `--resume` and continuation prompt
- All retries exhausted: yields `session.failed` event
- Pause/resume still works (paused session yields `session.paused` event)
- Events from stdout are correctly parsed and yielded
- Multiple sessions are independently tracked

### Unit: ClaudeCodeParser system.init handling

- `system.init` event is parsed into `session.started` with `claude_session_id` and `model`
- Existing event types (assistant, tool_use, tool_result, etc.) still parse correctly

### Integration: Engine protocol compliance

- `ClaudeCodeEngine` satisfies `EngineAdapter` protocol (isinstance check)
- All 8 protocol methods exist and are callable
- `_build_engine("claude_code")` returns the refactored engine

### Integration: SSE streaming pipeline

- Mocked subprocess stdout flows through engine -> SSE generator -> `text/event-stream` response
- Error events from crashed subprocess appear in SSE stream

## Files to modify

- `backend/codehive/engine/claude_code.py` -- rewrite to fire-and-forget model
- `backend/codehive/engine/claude_code_engine.py` -- rewrite session state and send_message
- `backend/codehive/engine/claude_code_parser.py` -- add system.init handling
- `backend/tests/test_claude_code_engine.py` -- rewrite tests for new model
- `backend/tests/test_claude_code_wrapper.py` -- rewrite tests for new model

## Reference implementation

- `~/git/telegram-writing-assistant/claude_runner.py` -- `ClaudeRunner._run_command()` shows the fire-and-forget pattern with `-p`, `--resume`, `--output-format stream-json`
- `~/git/telegram-writing-assistant/session_retrier.py` -- `SessionRetrier.run_with_auto_retry()` shows the retry loop pattern

## Notes

- The `EngineAdapter` protocol does NOT change. Only the internal implementation changes.
- The web frontend does NOT change. It already consumes SSE events from `/messages/stream`.
- The `_build_engine()` helper in `sessions.py` does NOT need changes -- it already constructs `ClaudeCodeEngine` with `working_dir`.
- Claude Code's `-p` flag makes the process non-interactive (single prompt, exit when done). This is fundamentally different from the current `--input-format stream-json` approach.
- The `--resume` flag gives us conversation continuity without needing to maintain a long-running process.

## Log

### [SWE] 2026-03-19 00:25

- Rewrote `ClaudeCodeProcess` from long-running interactive process (stdin pipes, `--input-format stream-json`) to fire-and-forget model (`claude -p "{message}" --output-format stream-json --verbose`). The `run()` method is now an async generator that spawns a subprocess per invocation, yields stdout lines, and raises `ClaudeProcessError` on non-zero exit.
- Rewrote `ClaudeCodeEngine._SessionState` to hold `claude_session_id` (from `system.init` events) and `retry_count` instead of a live `ClaudeCodeProcess` instance. No subprocess is spawned until `send_message()` is called.
- `send_message()` now: builds a `ClaudeCodeProcess` per call, adds `--resume {session_id}` for subsequent messages, captures `claude_session_id` from `session.started` events, and auto-retries up to 3 times on crash with a continuation prompt.
- Updated `ClaudeCodeParser` to handle `system.init` events (type="system", subtype="init") by emitting `session.started` events with `claude_session_id` and `model` fields. Non-init system messages still produce `session.error`.
- `EngineAdapter` protocol interface is unchanged. `_build_engine()` in sessions.py is unchanged.
- Files modified:
  - `backend/codehive/engine/claude_code.py` -- complete rewrite
  - `backend/codehive/engine/claude_code_engine.py` -- complete rewrite
  - `backend/codehive/engine/claude_code_parser.py` -- added system.init handling
  - `backend/tests/test_claude_code_wrapper.py` -- rewritten for new model
  - `backend/tests/test_claude_code_engine.py` -- rewritten for new model
- Tests added: 55 tests covering process, parser, engine, retry, pause/resume, protocol compliance, pipeline integration
- Build results: 1894 passed, 2 pre-existing failures in test_cli.py (unrelated -- those tests use MagicMock instead of AsyncMock for create_session), 3 skipped, ruff clean, tsc clean, vitest 645 passed
- Known limitations: 2 pre-existing test failures in `tests/test_cli.py::TestMessagesEndpointIntegration` are unrelated to this change (they use `MagicMock()` for an async engine, causing `await` to fail on `create_session`)

### [QA] 2026-03-19 00:35

**Test Results:**
- Claude Code tests (test_claude_code_wrapper.py + test_claude_code_engine.py): 55 passed, 0 failed
- All backend tests: 1894 passed, 2 failed (pre-existing in test_cli.py, confirmed same failures on clean main), 3 skipped
- Frontend tests (vitest): 645 passed, 0 failed
- Ruff check: clean
- Ruff format: clean (253 files already formatted)
- TypeScript (tsc --noEmit): clean

**Acceptance Criteria:**

1. `ClaudeCodeProcess` no longer uses `--input-format stream-json` or stdin pipes. Uses `claude -p "{message}" --output-format stream-json --verbose` per invocation. -- PASS (verified in claude_code.py `_build_command()` lines 44-55; test `test_run_spawns_with_correct_flags` asserts `--input-format` not in args)

2. `ClaudeCodeProcess` accepts optional `resume_session_id` and adds `--resume {id}`. -- PASS (parameter on `run()` line 62; `_build_command()` lines 52-53; test `test_run_with_resume_session_id` confirms)

3. `ClaudeCodeEngine.send_message()` captures `session_id` from `system.init` events and stores it for `--resume`. -- PASS (lines 106-109 in claude_code_engine.py; test `test_first_message_no_resume` asserts `claude_session_id == "cs-xyz"` after send)

4. `ClaudeCodeEngine.send_message()` auto-retries on non-zero exit up to 3 times with `--resume`. -- PASS (`_retry_loop` method lines 124-183; tests: `test_crash_retries_with_resume`, `test_all_retries_exhausted_yields_session_failed`, `test_retry_resets_count_on_success`)

5. `ClaudeCodeEngine.send_message()` yields `session.failed` after all retries exhausted. -- PASS (line 179; test `test_all_retries_exhausted_yields_session_failed` asserts "retries exhausted" in error)

6. `ClaudeCodeParser` handles `system.init` events and emits `session.started` with `claude_session_id` and `model`. -- PASS (parser lines 121-129; tests `test_parse_system_init`, `test_parse_system_init_missing_fields`)

7. `EngineAdapter` protocol interface unchanged. -- PASS (test `test_isinstance_check` confirms `isinstance(engine, EngineAdapter)` is True; test `test_all_protocol_methods_exist` checks all 8 methods)

8. SSE streaming endpoint still works with new engine. -- PASS (test `test_full_pipeline_events` feeds mocked stream-json through engine and collects 5 correct events; test `test_sse_pipeline_with_error` verifies error events flow through)

9. 15+ tests covering new engine behavior. -- PASS (55 tests total across both files)

10. Ruff clean. -- PASS

**Key behaviors verified in tests:**
- First message spawns without `--resume` (test_first_message_no_resume)
- Second message uses `--resume` with captured session_id (test_second_message_uses_resume)
- Crash triggers auto-retry up to 3 times (test_crash_retries_with_resume, test_all_retries_exhausted)
- Crash without session_id yields immediate failure (test_crash_without_session_id_yields_failed)
- system.init captures claude_session_id (test_parse_system_init, test_first_message_no_resume)
- Multiple sessions tracked independently (test_independent_sessions)
- Pause/resume works (test_send_message_while_paused_yields_paused_event)

**Code quality notes:**
- Clean type hints throughout
- Proper error handling with custom ClaudeProcessError exception
- No hardcoded values (MAX_RETRIES and CONTINUATION_PROMPT are module-level constants)
- Follows existing codebase patterns (async generators, EngineAdapter protocol)
- No unnecessary dependencies added

**VERDICT: PASS**

### [PM] 2026-03-19 01:00

- Reviewed diff: 5 files changed (3 source, 2 test) -- 808 insertions, 608 deletions
- Ran tests independently: 55 passed in 0.91s
- Ruff check: clean
- Code review: implementation follows fire-and-forget pattern from reference, clean architecture, proper error handling
- Acceptance criteria: all 10/10 met
  1. No --input-format or stdin pipes -- PASS (claude_code.py uses -p flag)
  2. resume_session_id with --resume -- PASS (_build_command lines 52-53)
  3. session_id capture from system.init -- PASS (engine lines 106-109)
  4. Auto-retry up to 3 times -- PASS (_retry_loop method)
  5. session.failed after retries exhausted -- PASS (line 179)
  6. Parser handles system.init -- PASS (parser lines 120-129)
  7. EngineAdapter protocol unchanged -- PASS (base.py untouched, isinstance test passes)
  8. SSE streaming works -- PASS (pipeline integration tests verify)
  9. 55 tests (15+ required) -- PASS
  10. Ruff clean -- PASS
- No scope dropped, no follow-up issues needed
- VERDICT: ACCEPT
