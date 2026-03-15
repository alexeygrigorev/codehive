# 33: Claude Code CLI Wrapper and Event Parser

## Description
Build a wrapper around the Claude Code CLI (`claude`) that spawns it as a subprocess per session, captures its stdout/stderr output, and parses it into codehive's unified event format.

This issue covers the low-level process management and output parsing only. The full EngineAdapter implementation (create_session, send_message, start_task, etc.) is handled in #34.

## Scope
- `backend/codehive/engine/claude_code.py` -- Claude Code CLI process manager: spawn, send input via stdin, capture output, terminate
- `backend/codehive/engine/claude_code_parser.py` -- Parse Claude Code CLI `stream-json` output into codehive events (message.created, tool.call.started, tool.call.finished, file.changed, etc.)
- `backend/tests/test_claude_code_wrapper.py` -- Wrapper and parser tests (with mocked CLI output)

## Behavior

### Process Manager (`ClaudeCodeProcess`)
- Spawns `claude --print --output-format stream-json --input-format stream-json` as an async subprocess per session
- Sends user messages to the process via stdin as newline-delimited JSON
- Reads stdout line-by-line and feeds each JSON object to the parser
- Captures stderr for error reporting / logging
- Provides methods: `start()`, `send(message: str)`, `stop()`, `is_alive() -> bool`
- On unexpected process exit (crash), emits a `session.failed` event with stderr contents
- Supports configurable CLI path (default: `claude`) and additional CLI flags (e.g. `--model`, `--allowedTools`, `--permission-mode`, `--system-prompt`)
- Each process is associated with a session_id and optionally a working directory (project root)

### Event Parser (`ClaudeCodeParser`)
- Takes a single line of stream-json output and returns zero or more codehive event dicts
- Maps Claude Code output message types to codehive event types:
  - Assistant text messages -> `message.created` (role: assistant)
  - Tool use blocks -> `tool.call.started` (with tool_name and tool_input)
  - Tool results -> `tool.call.finished` (with tool_name and result content)
  - File change notifications -> `file.changed` (with path)
  - Errors / system messages -> `session.error`
- Returns dicts with at least `type` and `session_id` keys, matching the format used by `NativeEngine`
- Handles malformed / unexpected JSON gracefully (logs warning, skips line)
- Is a pure function / stateless class -- no side effects, easy to unit test

## Out of Scope (handled in #34)
- Full `EngineAdapter` protocol implementation (create_session, pause, resume, approve_action, etc.)
- Integration with the session API routes
- Engine selection in session creation

## Dependencies
- Depends on: #07 (event bus for publishing parsed events) -- DONE
- Depends on: #09 (engine adapter interface, for type alignment) -- DONE

## Acceptance Criteria

- [ ] `ClaudeCodeProcess` class exists in `backend/codehive/engine/claude_code.py` with methods: `start()`, `send(message)`, `stop()`, `is_alive()`
- [ ] `ClaudeCodeParser` class exists in `backend/codehive/engine/claude_code_parser.py` with a `parse_line(line: str, session_id: uuid.UUID) -> list[dict]` method
- [ ] Parser converts assistant text messages into `{"type": "message.created", "role": "assistant", ...}` events
- [ ] Parser converts tool use into `{"type": "tool.call.started", "tool_name": ..., "tool_input": ...}` events
- [ ] Parser converts tool results into `{"type": "tool.call.finished", "tool_name": ..., "result": ...}` events
- [ ] Parser handles malformed JSON input without raising exceptions (logs and returns empty list)
- [ ] Process manager spawns `claude` with `--print --output-format stream-json` flags
- [ ] Process manager sends messages via stdin as newline-delimited JSON
- [ ] Process manager detects unexpected process exit and produces a `session.failed` event dict
- [ ] Process manager supports configurable CLI path and extra flags via constructor arguments
- [ ] `uv run pytest backend/tests/test_claude_code_wrapper.py -v` passes with 10+ tests
- [ ] All tests use mocked subprocess -- no real `claude` CLI invocation during tests

## Test Scenarios

### Unit: ClaudeCodeParser
- Parse a stream-json line containing an assistant text message, verify `message.created` event with correct content and role
- Parse a stream-json line containing a tool_use block, verify `tool.call.started` event with tool_name and tool_input
- Parse a stream-json line containing a tool result, verify `tool.call.finished` event with result content
- Parse a malformed JSON line, verify empty list returned and no exception raised
- Parse an empty string, verify empty list returned
- Parse an unrecognized message type, verify it is skipped or mapped to a generic event
- Verify all returned events include `session_id` and `type` keys

### Unit: ClaudeCodeProcess
- Start process with mocked asyncio.create_subprocess_exec, verify `claude` is called with correct flags
- Send a message via `send()`, verify it appears on the mocked stdin as newline-delimited JSON
- Simulate process stdout producing stream-json lines, verify they are readable from the process
- Call `stop()`, verify the subprocess is terminated
- Call `is_alive()` on a running mock process, verify True; on a stopped process, verify False
- Simulate a process crash (returncode != 0), verify a `session.failed`-style error is detectable
- Verify configurable CLI path: instantiate with custom path, verify it is used in the spawn command
- Verify extra CLI flags (e.g. `--model opus`) are passed through to the subprocess

### Integration: Process + Parser together
- Feed mocked stream-json lines through the process stdout, pipe through the parser, verify the full event list matches expected codehive events

## Log

### [SWE] 2026-03-15 10:00
- Implemented ClaudeCodeProcess in `backend/codehive/engine/claude_code.py`: async subprocess manager with start(), send(), stop(), is_alive(), read_stdout_line(), read_stderr(), check_for_crash() methods. Supports configurable cli_path, working_dir, and extra_flags. Spawns `claude --print --output-format stream-json --input-format stream-json`.
- Implemented ClaudeCodeParser in `backend/codehive/engine/claude_code_parser.py`: stateless parser with parse_line(line, session_id) -> list[dict]. Maps assistant, tool_use, tool_result, content_block_delta, error, system, and result message types to codehive event format (message.created, tool.call.started, tool.call.finished, file.changed, session.error). Handles malformed JSON gracefully.
- Event dicts match the NativeEngine format: all include `type` and `session_id` keys, plus role-specific fields.
- Files created: `backend/codehive/engine/claude_code.py`, `backend/codehive/engine/claude_code_parser.py`, `backend/tests/test_claude_code_wrapper.py`
- Tests added: 30 tests total (15 parser unit tests, 14 process manager unit tests, 1 integration test). All use mocked subprocess, no real CLI invocation.
- Build results: 30 tests pass, 0 fail, ruff clean

### [QA] 2026-03-15 11:00
- Tests: 30 passed, 0 failed (full suite: 486 passed, 0 failed)
- Ruff check: clean (0 issues)
- Ruff format: clean (3 files already formatted)
- AC 1: PASS -- ClaudeCodeProcess class in claude_code.py with start(), send(), stop(), is_alive()
- AC 2: PASS -- ClaudeCodeParser class in claude_code_parser.py with parse_line(line, session_id) -> list[dict]
- AC 3: PASS -- Parser maps assistant text to message.created with role=assistant
- AC 4: PASS -- Parser maps tool_use to tool.call.started with tool_name and tool_input
- AC 5: PASS -- Parser maps tool_result to tool.call.finished with tool_name and result
- AC 6: PASS -- Malformed JSON returns empty list, no exception (tested: invalid JSON, empty string, non-dict JSON)
- AC 7: PASS -- Spawns with --print --output-format stream-json --input-format stream-json
- AC 8: PASS -- send() writes JSON + newline to stdin, drain awaited
- AC 9: PASS -- check_for_crash() returns session.failed dict with exit_code and stderr error
- AC 10: PASS -- Constructor accepts cli_path and extra_flags, both passed to subprocess
- AC 11: PASS -- 30 tests pass (exceeds 10+ requirement)
- AC 12: PASS -- All process tests patch asyncio.create_subprocess_exec, no real CLI invocation
- VERDICT: PASS

### [PM] 2026-03-15 12:15
- Reviewed diff: 3 new files (claude_code.py: 178 lines, claude_code_parser.py: 171 lines, test_claude_code_wrapper.py: 511 lines)
- Results verified: 30/30 tests pass in 0.54s, ruff clean, real test output confirmed
- Code review findings:
  - Clean separation: process manager (claude_code.py) and parser (claude_code_parser.py) are independent modules
  - Parser is stateless as specified, no side effects
  - Event dicts align with NativeEngine format (type + session_id keys present in all events)
  - Process manager has proper lifecycle: start/send/stop/is_alive plus useful helpers (read_stdout_line, read_stderr, check_for_crash)
  - Graceful shutdown: stop() uses SIGTERM with 5s timeout before escalating to SIGKILL
  - Parser handles 7 message types: assistant, tool_use, tool_result, content_block_delta, error, system, result
  - _extract_text_content helper correctly handles both string and content-block-list formats
  - Tests are meaningful: each tests a specific behavior, not just smoke tests
  - All process tests properly mock asyncio.create_subprocess_exec
  - Integration test validates the full pipeline: stdout lines through parser to codehive events
- Acceptance criteria: all 12 met
  - AC 1: PASS -- ClaudeCodeProcess with start(), send(), stop(), is_alive()
  - AC 2: PASS -- ClaudeCodeParser with parse_line(line, session_id) -> list[dict]
  - AC 3: PASS -- assistant text -> message.created with role=assistant
  - AC 4: PASS -- tool_use -> tool.call.started with tool_name and tool_input
  - AC 5: PASS -- tool_result -> tool.call.finished with tool_name and result
  - AC 6: PASS -- malformed JSON returns empty list, no exception
  - AC 7: PASS -- spawns with --print --output-format stream-json --input-format stream-json
  - AC 8: PASS -- stdin newline-delimited JSON with drain
  - AC 9: PASS -- session.failed event on crash with exit_code and stderr
  - AC 10: PASS -- configurable cli_path and extra_flags
  - AC 11: PASS -- 30 tests (exceeds 10+ requirement)
  - AC 12: PASS -- all tests mock subprocess, no real CLI invocation
- Follow-up issues created: none needed, scope is clean
- VERDICT: ACCEPT
