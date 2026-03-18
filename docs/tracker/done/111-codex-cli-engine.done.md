# Issue #111: Create CodexCLIEngine for `codex` CLI subprocess

## Background

Split from #110. After #110 cleans up the config and provider detection, the Codex provider needs an actual CLI-based engine (like ClaudeCodeEngine wraps the `claude` CLI). The OpenAI Codex CLI (`@openai/codex`) provides a `codex exec` subcommand for non-interactive execution with `--json` JSONL output, which is analogous to the `claude --print --output-format stream-json` pattern already used by ClaudeCodeEngine.

## Dependencies

- #110 must be `.done.md` first (config cleanup, provider detection) -- DONE

## Scope

This issue creates three new files mirroring the existing Claude Code engine trio:

| Claude Code (existing) | Codex CLI (new) |
|---|---|
| `claude_code.py` (ClaudeCodeProcess) | `codex_cli_process.py` (CodexCLIProcess) |
| `claude_code_parser.py` (ClaudeCodeParser) | `codex_cli_parser.py` (CodexCLIParser) |
| `claude_code_engine.py` (ClaudeCodeEngine) | `codex_cli_engine.py` (CodexCLIEngine) |

Plus wiring in `_build_engine()` in `sessions.py`.

The existing `CodexEngine` (OpenAI SDK-based, in `codex.py`) remains unchanged.

## Requirements

### 1. CodexCLIProcess (`backend/codehive/engine/codex_cli_process.py`)

Manages a single `codex exec` CLI subprocess for one session. Mirrors `ClaudeCodeProcess`.

- Spawns `codex exec --json --full-auto -C <working_dir>` as an async subprocess
- The prompt is passed as a positional argument to `codex exec` (not via stdin streaming like Claude Code)
- Since `codex exec` is non-interactive (one prompt in, runs to completion), each `send()` call spawns a new `codex exec` subprocess rather than writing to an existing stdin
- Reads stdout line-by-line (JSONL events)
- Supports `--model` flag via constructor parameter (default: `codex-mini-latest`)
- Supports extra CLI flags (e.g. `--sandbox`, custom `-c` config overrides)
- Handles process lifecycle: start, is_alive, stop (SIGTERM with 5s timeout, then SIGKILL)
- Collects stderr for crash diagnostics
- `check_for_crash()` returns a `session.failed` event dict on non-zero exit

### 2. CodexCLIParser (`backend/codehive/engine/codex_cli_parser.py`)

Stateless parser that converts Codex CLI JSONL output into codehive event dicts. Mirrors `ClaudeCodeParser`.

- Parses each JSONL line from `codex exec --json` stdout
- Maps Codex event types to codehive event types:
  - Agent text messages -> `message.created` / `message.delta`
  - Tool/command execution starts -> `tool.call.started`
  - Tool/command execution results -> `tool.call.finished`
  - File changes -> `file.changed`
  - Errors -> `session.error`
  - Final result/completion -> `message.created`
- Returns `list[dict]` per line (zero or more events), same contract as `ClaudeCodeParser.parse_line()`
- Handles malformed JSON gracefully (log warning, return empty list)
- Since the exact JSONL schema from `codex exec --json` may vary across versions, the parser should be defensive: log and skip unrecognized event types rather than crashing

### 3. CodexCLIEngine (`backend/codehive/engine/codex_cli_engine.py`)

Engine adapter using the Codex CLI subprocess. Mirrors `ClaudeCodeEngine`. Implements the `EngineAdapter` protocol.

Constructor parameters:
- `diff_service: DiffService`
- `cli_path: str = "codex"` (path to the codex binary)
- `working_dir: str | None = None`
- `model: str = "codex-mini-latest"`
- `extra_flags: list[str] | None = None`

Methods (all from EngineAdapter protocol):
- `create_session(session_id)` -- initialize internal session state (no subprocess spawned yet since codex exec is per-invocation)
- `send_message(session_id, message)` -- spawn a `codex exec` subprocess with the message as prompt, read JSONL stdout, parse via CodexCLIParser, yield codehive events
- `start_task(session_id, task_id)` -- fetch task instructions and delegate to `send_message`
- `pause(session_id)` / `resume(session_id)` -- set/clear pause flag
- `approve_action(session_id, action_id)` / `reject_action(session_id, action_id)` -- store action decisions
- `get_diff(session_id)` -- delegate to DiffService
- `cleanup_session(session_id)` -- stop any running process, remove session state

### 4. Wire into `_build_engine()` (`backend/codehive/api/routes/sessions.py`)

- Add `engine_type == "codex_cli"` branch that constructs and returns a `CodexCLIEngine`
- Uses `working_dir` from `session_config["project_root"]`
- The existing `engine_type == "codex"` branch (SDK-based CodexEngine) remains unchanged

## User Stories

Since this is a backend engine with no UI changes, the user stories are from the developer/operator perspective.

### Story: Developer creates a session using the Codex CLI engine
1. Developer creates a session via API with `engine: "codex_cli"`
2. Developer sends a message to the session via `POST /api/sessions/{id}/messages`
3. The backend spawns a `codex exec --json --full-auto` subprocess
4. JSONL events stream from the subprocess
5. The API returns parsed codehive events (message.created, tool.call.started, tool.call.finished, etc.)
6. Events have the same shape as ClaudeCodeEngine events -- the UI does not need to change

### Story: Developer uses SSE streaming with CodexCLIEngine
1. Developer sends a message via `POST /api/sessions/{id}/messages/stream`
2. The backend spawns `codex exec` and reads JSONL output line by line
3. Each parsed event is yielded as an SSE `data:` frame
4. When the codex process exits cleanly, the stream ends
5. If the process crashes, a `session.failed` event is yielded

### Story: Developer pauses and resumes a CodexCLI session
1. Developer calls `POST /api/sessions/{id}/pause`
2. Subsequent `send_message` calls return a `session.paused` event immediately
3. Developer calls `POST /api/sessions/{id}/resume`
4. Next `send_message` call proceeds normally

## Acceptance Criteria

- [ ] `CodexCLIProcess` spawns `codex exec --json --full-auto` with correct flags
- [ ] `CodexCLIProcess` reads stdout line-by-line and supports `check_for_crash()`
- [ ] `CodexCLIParser.parse_line()` converts JSONL to codehive event dicts
- [ ] `CodexCLIParser` handles malformed JSON without crashing (returns empty list)
- [ ] `CodexCLIParser` handles unrecognized event types without crashing (returns empty list)
- [ ] `CodexCLIEngine` implements the `EngineAdapter` protocol (`isinstance` check passes)
- [ ] `CodexCLIEngine` has all 8 protocol methods: create_session, send_message, start_task, pause, resume, approve_action, reject_action, get_diff
- [ ] `CodexCLIEngine.send_message()` yields codehive events parsed from subprocess JSONL output
- [ ] `CodexCLIEngine.send_message()` yields `session.failed` on subprocess crash
- [ ] `CodexCLIEngine.send_message()` yields `session.paused` when session is paused
- [ ] `CodexCLIEngine.cleanup_session()` stops the process and removes state
- [ ] `_build_engine()` returns `CodexCLIEngine` for `engine_type="codex_cli"`
- [ ] `_build_engine()` still returns `CodexEngine` for `engine_type="codex"` (no regression)
- [ ] `_build_engine()` still returns `ClaudeCodeEngine` for `engine_type="claude_code"` (no regression)
- [ ] `uv run pytest tests/ -v` passes with 15+ new tests (process, parser, engine, wiring)
- [ ] `uv run ruff check` is clean
- [ ] All tests use mocked subprocess -- no real `codex` CLI invocation required

## Test Scenarios

### Unit: CodexCLIProcess
- `_build_command()` returns correct command list with default flags
- `_build_command()` includes `--model` flag when model is specified
- `_build_command()` includes `-C` flag when working_dir is set
- `_build_command()` includes extra_flags
- `start()` creates async subprocess with correct args
- `read_stdout_line()` returns decoded lines
- `read_stdout_line()` returns None on EOF
- `check_for_crash()` returns session.failed event on non-zero exit
- `check_for_crash()` returns None when process is still running or exited cleanly
- `stop()` terminates process gracefully, kills on timeout

### Unit: CodexCLIParser
- Parses agent text message into `message.created` event
- Parses tool/command start into `tool.call.started` event
- Parses tool/command result into `tool.call.finished` event
- Parses error into `session.error` event
- Returns empty list for blank lines
- Returns empty list for malformed JSON
- Returns empty list for unrecognized event types
- All returned events include `session_id`

### Unit: CodexCLIEngine
- `isinstance(engine, EngineAdapter)` is True
- All 8 protocol methods exist and are callable
- `create_session()` initializes session state
- `send_message()` yields parsed events from mocked subprocess output
- `send_message()` on non-existent session raises KeyError
- `send_message()` on crashed process yields `session.failed`
- `send_message()` while paused yields `session.paused`
- `pause()` / `resume()` toggle the paused flag
- `start_task()` delegates to `send_message()`
- `get_diff()` returns DiffService data
- `cleanup_session()` stops process and removes state

### Integration: Engine wiring
- `_build_engine(config, engine_type="codex_cli")` returns CodexCLIEngine
- `_build_engine(config, engine_type="codex")` still returns CodexEngine (regression check)
- `_build_engine(config, engine_type="claude_code")` still returns ClaudeCodeEngine (regression check)
- `_build_engine(config, engine_type="unknown")` raises HTTPException 400

## Implementation Notes

- The `codex exec` CLI is non-interactive: it takes a prompt as a positional arg (or from stdin), runs to completion, then exits. This differs from Claude Code which is a long-running process with stdin/stdout streaming. Each `send_message()` call should spawn a fresh `codex exec` subprocess.
- The `--json` flag makes `codex exec` output JSONL events to stdout. The exact event schema needs to be discovered during implementation by running `codex exec --json "hello" 2>/dev/null` and inspecting the output. The parser should be written defensively.
- Use `--full-auto` to avoid interactive approval prompts (sandbox write + on-request approval).
- The `codex` CLI is a Node.js tool installed via `npm install -g @openai/codex`. The `cli_path` defaults to `"codex"` assuming it is on PATH, but can be overridden (e.g., to `npx @openai/codex`).
- Follow the exact same test patterns as `test_claude_code_engine.py` -- mocked subprocess, no real CLI needed.

## Log

### [SWE] 2026-03-18 20:35
- Created CodexCLIProcess (codex_cli_process.py): manages `codex exec` subprocess lifecycle, spawns fresh process per send() call, builds command with --json --full-auto --model -C flags, handles stop/is_alive/check_for_crash
- Created CodexCLIParser (codex_cli_parser.py): stateless JSONL parser mapping Codex CLI events to codehive event dicts (message.created, tool.call.started, tool.call.finished, file.changed, session.error, message.delta), defensive against malformed JSON and unknown event types
- Created CodexCLIEngine (codex_cli_engine.py): EngineAdapter implementation wrapping process + parser, all 8 protocol methods (create_session, send_message, start_task, pause, resume, approve_action, reject_action, get_diff), plus cleanup_session
- Wired `engine_type="codex_cli"` into `_build_engine()` in sessions.py
- Updated engine/__init__.py to export CodexCLIEngine
- Files created: backend/codehive/engine/codex_cli_process.py, backend/codehive/engine/codex_cli_parser.py, backend/codehive/engine/codex_cli_engine.py, backend/tests/test_codex_cli_engine.py
- Files modified: backend/codehive/api/routes/sessions.py, backend/codehive/engine/__init__.py
- Tests added: 49 tests covering process (13), parser (13), engine protocol/create/send/pause/approve/diff/task/cleanup (19), wiring (4)
- Build results: 49 new tests pass, 1855 total backend tests pass (7 pre-existing CI pipeline failures unrelated), ruff clean, tsc clean, 613 web tests pass
- E2E tests: NOT RUN -- `codex` CLI is not installed on this machine. All tests use mocked subprocess.
- Known limitations: Parser event type mappings are based on documented/expected Codex CLI JSONL schema; actual output may vary across codex versions and will need tuning when tested against real CLI

### [QA] 2026-03-18 20:40
- Codex CLI tests: 49 passed, 0 failed (test_codex_cli_engine.py)
- All backend tests: 1855 passed, 7 failed (pre-existing CI pipeline tests, unrelated), 3 skipped
- Frontend tests: 613 passed (107 test files)
- Ruff check: clean (All checks passed!)
- Ruff format: clean (248 files already formatted)
- tsc --noEmit: clean (no output)
- E2E: NOT RUN -- codex CLI not installed. All tests use mocked subprocess. Accepted per issue scope.
- Acceptance criteria:
  - [x] CodexCLIProcess spawns `codex exec --json --full-auto` with correct flags -- PASS (test_build_command_default_flags, test_send_creates_subprocess verify cmd args)
  - [x] CodexCLIProcess reads stdout line-by-line and supports check_for_crash() -- PASS (test_read_stdout_line_returns_decoded, test_check_for_crash_returns_session_failed)
  - [x] CodexCLIParser.parse_line() converts JSONL to codehive event dicts -- PASS (test_parse_agent_text_message, test_parse_tool_call_started, test_parse_tool_result_finished)
  - [x] CodexCLIParser handles malformed JSON without crashing -- PASS (test_parse_malformed_json returns [])
  - [x] CodexCLIParser handles unrecognized event types without crashing -- PASS (test_parse_unrecognized_type returns [])
  - [x] CodexCLIEngine implements EngineAdapter protocol -- PASS (test_isinstance_check: isinstance(engine, EngineAdapter) is True)
  - [x] CodexCLIEngine has all 8 protocol methods -- PASS (test_all_protocol_methods_exist checks all 8)
  - [x] CodexCLIEngine.send_message() yields codehive events from subprocess JSONL -- PASS (test_send_message_yields_events, test_full_pipeline_events)
  - [x] CodexCLIEngine.send_message() yields session.failed on crash -- PASS (test_send_message_process_crash)
  - [x] CodexCLIEngine.send_message() yields session.paused when paused -- PASS (test_send_message_while_paused_yields_paused_event)
  - [x] CodexCLIEngine.cleanup_session() stops process and removes state -- PASS (test_cleanup_session_removes_state, test_cleanup_session_stops_process)
  - [x] _build_engine() returns CodexCLIEngine for engine_type="codex_cli" -- PASS (test_build_engine_returns_codex_cli_engine)
  - [x] _build_engine() still returns CodexEngine for engine_type="codex" -- PASS (test_build_engine_codex_still_works)
  - [x] _build_engine() still returns ClaudeCodeEngine for engine_type="claude_code" -- PASS (test_build_engine_claude_code_still_works)
  - [x] 15+ new tests with mocked subprocess -- PASS (49 tests, all mocked)
  - [x] ruff check clean -- PASS
  - [x] All tests use mocked subprocess -- PASS (verified: all tests patch asyncio.create_subprocess_exec)
- Code quality: type hints used throughout, follows existing ClaudeCodeEngine patterns, defensive parser with logging, proper error handling
- VERDICT: PASS

### [PM] 2026-03-18 20:50
- Reviewed diff: 6 files changed (3 new engine files, 1 new test file, 2 modified: sessions.py, engine/__init__.py)
- Ran tests independently: 49/49 passed in 1.04s
- Results verified: all tests use mocked subprocess; E2E NOT RUN (codex CLI not installed -- acceptable per scope)
- Acceptance criteria review (17/17):
  - [x] CodexCLIProcess spawns `codex exec --json --full-auto` with correct flags -- verified in _build_command() and tests
  - [x] CodexCLIProcess reads stdout line-by-line and supports check_for_crash() -- verified in code and 5 tests
  - [x] CodexCLIParser.parse_line() converts JSONL to codehive event dicts -- verified: handles message, tool_call, tool_result, file_change, error types
  - [x] CodexCLIParser handles malformed JSON without crashing -- verified: returns empty list, logs warning
  - [x] CodexCLIParser handles unrecognized event types without crashing -- verified: returns empty list, logs debug
  - [x] CodexCLIEngine implements EngineAdapter protocol -- verified: isinstance check test passes
  - [x] CodexCLIEngine has all 8 protocol methods -- verified: test_all_protocol_methods_exist checks all 8
  - [x] send_message() yields codehive events from subprocess JSONL -- verified: test_send_message_yields_events + test_full_pipeline_events
  - [x] send_message() yields session.failed on crash -- verified: test_send_message_process_crash
  - [x] send_message() yields session.paused when paused -- verified: test_send_message_while_paused_yields_paused_event
  - [x] cleanup_session() stops process and removes state -- verified: 2 cleanup tests
  - [x] _build_engine() returns CodexCLIEngine for engine_type="codex_cli" -- verified: wiring test passes
  - [x] _build_engine() returns CodexEngine for engine_type="codex" -- verified: regression test passes
  - [x] _build_engine() returns ClaudeCodeEngine for engine_type="claude_code" -- verified: regression test passes
  - [x] 15+ new tests with mocked subprocess -- verified: 49 tests, all mocked
  - [x] ruff check clean -- verified by QA
  - [x] All tests use mocked subprocess -- verified: no real codex CLI invocation
- Code quality: clean, well-documented, mirrors ClaudeCodeEngine patterns exactly. Defensive parser handles unknown event types gracefully. Process lifecycle (SIGTERM -> 5s timeout -> SIGKILL) is correct.
- No scope dropped, no descoped items.
- User perspective: this is a backend engine with no UI -- the user will interact with it via API when codex CLI is installed. The mocked tests prove the contract is correct.
- VERDICT: ACCEPT
