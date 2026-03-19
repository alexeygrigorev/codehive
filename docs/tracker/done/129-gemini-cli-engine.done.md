# Issue #129: Add Gemini CLI as an engine option

## Problem

Google's Gemini CLI is installed and supports coding agent tasks with the same fire-and-forget subprocess pattern as Claude Code, Codex CLI, and Copilot CLI. Codehive should support it as a provider so users with Gemini CLI installed can use it to power sessions.

## Research Results (PM grooming 2026-03-19)

### Gemini CLI JSONL Event Structure

Captured from `gemini -p "..." --output-format stream-json --yolo`:

```jsonl
{"type":"init","timestamp":"2026-03-19T04:54:07.160Z","session_id":"cc70e0b5-356e-45ee-ba9d-ab691ed0c31e","model":"auto-gemini-3"}
{"type":"message","timestamp":"...","role":"user","content":"say hello"}
{"type":"message","timestamp":"...","role":"assistant","content":"Hello! I'm Gemini CLI,","delta":true}
{"type":"message","timestamp":"...","role":"assistant","content":" your autonomous engineering assistant.","delta":true}
{"type":"tool_use","timestamp":"...","tool_name":"run_shell_command","tool_id":"run_shell_command_1773896067962_0","parameters":{"description":"List files","command":"ls /tmp"}}
{"type":"tool_result","timestamp":"...","tool_id":"run_shell_command_1773896129178_0","status":"success"}
{"type":"tool_result","timestamp":"...","tool_id":"...","status":"error","output":"...","error":{"type":"invalid_tool_params","message":"..."}}
{"type":"result","timestamp":"...","status":"success","stats":{"total_tokens":11503,"input_tokens":11338,"output_tokens":57,"cached":0,"input":11338,"duration_ms":3375,"tool_calls":0,"models":{...}}}
```

### Event Type Summary

| Gemini Event | Codehive Mapping | Notes |
|---|---|---|
| `init` | `session.started` | Contains `session_id` (UUID) and `model`. Emitted first. |
| `message` (role=user) | Skip | Echo of user prompt, not needed. |
| `message` (role=assistant, delta=true) | `message.delta` | Streaming text chunk. |
| `message` (role=assistant, no delta) | `message.created` | Complete message (rare -- most are delta). |
| `tool_use` | `tool.call.started` | Has `tool_name`, `tool_id`, `parameters` (not `arguments`). |
| `tool_result` (status=success) | `tool.call.finished` | Has `tool_id`, optional `output`. |
| `tool_result` (status=error) | `tool.call.finished` | Has `error.message`. Prefix with "ERROR: ". |
| `result` | `session.completed` | Has `status`, `stats` with token usage and model breakdown. |

### Key Differences from Claude Code stream-json

1. **Init event**: Gemini emits `{"type":"init","session_id":"...","model":"..."}`. Claude emits `{"type":"system","subtype":"init","session_id":"...","model":"..."}`.
2. **Message streaming**: Gemini uses `{"type":"message","role":"assistant","delta":true}`. Claude uses `{"type":"content_block_delta","delta":{"type":"text_delta","text":"..."}}`.
3. **Tool events**: Gemini uses `tool_use` / `tool_result` with `parameters` (not `input`) and `tool_id`. Claude uses `tool_use` / `tool_result` with `input` and `name`.
4. **Result**: Gemini `result` has `status` + `stats` with per-model breakdown. Claude `result` has `modelUsage`.
5. **File tools**: Gemini uses `write_file`, `edit_file`, `read_file`. Same names as Claude.

### Resume Support

Confirmed working. The `init` event emits `session_id` (a UUID like `cc70e0b5-356e-45ee-ba9d-ab691ed0c31e`). Passing `--resume <session_id>` on subsequent calls correctly resumes context. Tested: asked "say hello" then resumed with "what did I say?" -- got "You said 'say hello'."

### CLI Flags

```
gemini -p "prompt" --output-format stream-json --yolo
gemini -p "prompt" --resume <session_id> --output-format stream-json --yolo
```

- `-p` -- non-interactive mode (required)
- `--output-format stream-json` -- JSONL streaming output
- `--yolo` / `-y` -- auto-approve all tools
- `--resume <id>` / `-r <id>` -- resume previous session
- `-m <model>` -- model selection
- `--sandbox` -- optional sandbox mode
- `--include-directories <dir>` -- additional workspace dirs (no `--cwd`; Gemini auto-detects from CWD)
- Working directory: set via subprocess `cwd` parameter (Gemini uses CWD as workspace root)

## Dependencies

- Issue #84 (provider configuration) -- `.done.md` (met)
- Issue #127 (copilot CLI engine) -- `.groomed.md` (NOT required as a dependency; pattern is already established by Claude Code and Codex CLI engines)

## Scope

### In Scope

1. `GeminiCLIProcess` -- subprocess manager (fire-and-forget per message)
2. `GeminiCLIParser` -- JSONL line parser mapping Gemini events to codehive events
3. `GeminiCLIEngine` -- engine adapter implementing `EngineAdapter` protocol
4. Provider detection via `shutil.which("gemini")` in `/api/providers`
5. Engine wiring in `_build_engine()` for `engine_type="gemini_cli"`
6. Engine export in `backend/codehive/engine/__init__.py`
7. Unit tests for all three classes + integration tests for wiring and provider detection

### Out of Scope

- UI changes to the provider dropdown (already generic, auto-populates from `/api/providers`)
- Model selection UI (future issue)
- Sandbox mode configuration (future issue)

## Files to Create

- `backend/codehive/engine/gemini_cli_process.py` -- GeminiCLIProcess + GeminiProcessError
- `backend/codehive/engine/gemini_cli_parser.py` -- GeminiCLIParser
- `backend/codehive/engine/gemini_cli_engine.py` -- GeminiCLIEngine
- `backend/tests/test_gemini_cli_engine.py` -- all tests

## Files to Modify

- `backend/codehive/engine/__init__.py` -- add GeminiCLIEngine export
- `backend/codehive/api/routes/providers.py` -- add gemini provider detection
- `backend/codehive/api/routes/sessions.py` -- add `gemini_cli` case in `_build_engine()`

## Acceptance Criteria

- [ ] `GeminiCLIProcess._build_command("hello")` returns `["gemini", "-p", "hello", "--output-format", "stream-json", "--yolo"]`
- [ ] `GeminiCLIProcess._build_command("hello", resume_session_id="abc-123")` includes `["--resume", "abc-123"]`
- [ ] `GeminiCLIProcess` sets `cwd` to `working_dir` (not `--add-dir` like Copilot)
- [ ] `GeminiCLIParser` maps `init` event to `session.started` with `gemini_session_id` and `model`
- [ ] `GeminiCLIParser` maps `message` (role=assistant, delta=true) to `message.delta`
- [ ] `GeminiCLIParser` maps `message` (role=assistant, no delta) to `message.created`
- [ ] `GeminiCLIParser` skips `message` (role=user) -- returns empty list
- [ ] `GeminiCLIParser` maps `tool_use` to `tool.call.started` with `tool_name` and `tool_input` (from `parameters`)
- [ ] `GeminiCLIParser` maps `tool_result` (status=success) to `tool.call.finished` with `result` from `output`
- [ ] `GeminiCLIParser` maps `tool_result` (status=error) to `tool.call.finished` with "ERROR: " prefix from `error.message`
- [ ] `GeminiCLIParser` maps `tool_result` for file-editing tools (`write_file`, `edit_file`) to also emit `file.changed`
- [ ] `GeminiCLIParser` maps `result` event to `session.completed` with `gemini_session_id` (from init), `usage` stats, and per-model breakdown
- [ ] `GeminiCLIParser` handles malformed JSON gracefully (returns empty list, no crash)
- [ ] `GeminiCLIParser` handles empty/blank lines gracefully
- [ ] Every event emitted by the parser includes `type` and `session_id` keys
- [ ] `GeminiCLIEngine` implements all 8 `EngineAdapter` protocol methods
- [ ] `isinstance(GeminiCLIEngine(...), EngineAdapter)` returns True
- [ ] `GeminiCLIEngine.send_message()` captures `gemini_session_id` from `init` event and uses it for `--resume` on subsequent calls
- [ ] `GeminiCLIEngine.send_message()` auto-retries on crash up to MAX_RETRIES using `--resume`
- [ ] `GeminiCLIEngine` pause/resume works (paused session yields `session.paused`)
- [ ] `GET /api/providers` includes a "gemini" provider with `type="cli"`
- [ ] Gemini provider shows `available=true` when `shutil.which("gemini")` finds the binary
- [ ] Gemini provider shows `available=false` when CLI is not on PATH
- [ ] `_build_engine(config, engine_type="gemini_cli")` returns a `GeminiCLIEngine` instance
- [ ] `uv run pytest tests/test_gemini_cli_engine.py -v` passes with 25+ tests
- [ ] `uv run ruff check` is clean
- [ ] Provider count in `/api/providers` is 6 (claude, codex, openai, zai, copilot, gemini)

## Test Scenarios

### Unit: GeminiCLIParser

- Parse `init` event -> `session.started` with `gemini_session_id` and `model`
- Parse `message` (assistant, delta=true) -> `message.delta` with content
- Parse `message` (assistant, delta=true, empty content) -> empty list
- Parse `message` (assistant, no delta field) -> `message.created`
- Parse `message` (role=user) -> empty list (skip user echo)
- Parse `tool_use` -> `tool.call.started` with `tool_name` and `tool_input` from `parameters`
- Parse `tool_result` (status=success) -> `tool.call.finished` with output
- Parse `tool_result` (status=success, no output field) -> `tool.call.finished` with empty result
- Parse `tool_result` (status=error) -> `tool.call.finished` with "ERROR: " prefix
- Parse `tool_result` for `write_file` -> `tool.call.finished` + `file.changed`
- Parse `tool_result` for `edit_file` -> `tool.call.finished` + `file.changed`
- Parse `result` event -> `session.completed` with stats and per-model usage
- Malformed JSON -> empty list, no crash
- Empty/blank line -> empty list
- Non-dict JSON (e.g. array) -> empty list
- All events include `type` and `session_id` keys

### Unit: GeminiCLIProcess

- `_build_command` basic: correct flags (`gemini`, `-p`, `--output-format`, `stream-json`, `--yolo`)
- `_build_command` with resume: includes `--resume <id>`
- `_build_command` without resume: no `--resume` flag
- `_build_command` with extra_flags: extra flags appended
- `run()` yields decoded stdout lines (mocked subprocess)
- `run()` raises `GeminiProcessError` on non-zero exit
- `run()` skips empty lines
- `run()` sets `cwd` to working_dir

### Unit: GeminiCLIEngine

- Protocol compliance: `isinstance(engine, EngineAdapter)` is True
- All 8 protocol methods exist and are callable
- `create_session` initializes state; duplicate call replaces state
- `send_message` yields parsed codehive events
- `send_message` captures `gemini_session_id` from `init` event
- `send_message` uses `--resume` on second call
- `send_message` on non-existent session raises `KeyError`
- `send_message` crash triggers auto-retry with `--resume`
- All retries exhausted yields `session.failed`
- Crash with no session ID yields `session.failed` immediately
- `pause()` / `resume()` toggle paused flag
- `send_message` while paused yields `session.paused`
- `approve_action` / `reject_action` mark pending actions
- `get_diff` delegates to DiffService
- `start_task` delegates to `send_message`
- `cleanup_session` removes state

### Integration: Engine wiring

- `_build_engine(config, engine_type="gemini_cli")` returns `GeminiCLIEngine`

### Integration: Provider detection

- `GET /api/providers` includes "gemini" with `available=true` when CLI found
- `GET /api/providers` includes "gemini" with `available=false` when CLI not found
- Provider count is 6

## Implementation Notes

### GeminiCLIProcess differences from CopilotCLIProcess

1. Output format: `stream-json` (not `json`)
2. Auto-approve flag: `--yolo` (not `--allow-all-tools --autopilot`)
3. No `--no-auto-update` needed
4. Working directory: use subprocess `cwd=` parameter (not `--add-dir`)
5. Resume: `--resume <id>` with space (not `--resume=<id>`)

### GeminiCLIParser differences from ClaudeCodeParser

1. `init` event (not `system` with `subtype=init`) contains `session_id`
2. Messages use `{"type":"message","role":"assistant","delta":true}` for streaming
3. Tool events: `tool_use` has `parameters` (not `input`), `tool_result` has `status` and `output` (not `content`)
4. `tool_result` error has nested `error.message` field
5. `result` event has `stats` (not `modelUsage`) with nested `models` dict
6. Tool identification for `file.changed`: match on `tool_name` from the corresponding `tool_use` via `tool_id` correlation, or match `tool_result` tool name extraction

### GeminiCLIParser session_id tracking

The `init` event is the only event that carries `session_id`. The parser should return it in the `session.started` event as `gemini_session_id`. The engine captures this and uses it for `--resume`. This is analogous to how `ClaudeCodeParser` returns `claude_session_id` from the `system/init` event.

### Tool ID correlation for file.changed

`tool_result` events do not repeat `tool_name` -- they only have `tool_id`. To emit `file.changed` for file-editing tools, the parser needs to track `tool_id -> tool_name` from `tool_use` events. This makes the parser slightly stateful (unlike the Copilot parser which gets `toolName` in both events). Add a `_tool_names: dict[str, str]` mapping to the parser, populated on `tool_use`, consumed on `tool_result`.

Additionally, `tool_result` for file tools may not include the file path. The parser should extract `file_path` from the stored `tool_use` parameters. Add `_tool_params: dict[str, dict]` to track parameters by `tool_id`.

## Log

### [SWE] 2026-03-19 06:10
- Implemented GeminiCLIProcess, GeminiCLIParser (stateful with tool_id tracking), and GeminiCLIEngine
- GeminiCLIProcess uses `cwd=working_dir` (not `--add-dir`), `--output-format stream-json`, `--yolo`, `--resume <id>` with space separator
- GeminiCLIParser tracks `_tool_names` and `_tool_params` dicts for tool_id -> tool_name/parameters correlation; emits `file.changed` for `write_file`/`edit_file` tools
- GeminiCLIParser captures `gemini_session_id` from `init` event (not `result` like Copilot)
- Each session state gets its own parser instance to maintain tool_id tracking per session
- Registered gemini provider in `/api/providers` with `shutil.which("gemini")` detection
- Added `gemini_cli` case in `_build_engine()`
- Exported GeminiCLIEngine in `engine/__init__.py`
- Updated test_providers_endpoint.py to expect 6 providers (was 5)
- Files created: `backend/codehive/engine/gemini_cli_process.py`, `backend/codehive/engine/gemini_cli_parser.py`, `backend/codehive/engine/gemini_cli_engine.py`, `backend/tests/test_gemini_cli_engine.py`
- Files modified: `backend/codehive/engine/__init__.py`, `backend/codehive/api/routes/providers.py`, `backend/codehive/api/routes/sessions.py`, `backend/tests/test_providers_endpoint.py`
- Tests added: 49 tests in test_gemini_cli_engine.py (16 parser, 9 process, 2 protocol, 2 create_session, 7 send_message, 3 pause/resume, 2 approve/reject, 2 get_diff, 1 start_task, 1 cleanup, 1 engine wiring, 3 provider detection)
- Build results: 49/49 gemini tests pass, all previously-passing tests still pass, ruff clean
- Pre-existing failures: 2 tests in test_cli.py (TestMessagesEndpointIntegration) fail before and after this change (unrelated mock issue)
- tsc --noEmit: clean, vitest: 681 passed

### [QA] 2026-03-19 06:25
- Tests: 49 passed, 0 failed (test_gemini_cli_engine.py); 73 passed combined with test_providers_endpoint.py
- Ruff check: clean; Ruff format: clean (267 files already formatted)
- Acceptance criteria walkthrough:
  - `_build_command("hello")` returns correct flags: PASS (test_build_command_basic)
  - `_build_command` with resume includes `--resume <id>`: PASS (test_build_command_with_resume)
  - `GeminiCLIProcess` sets `cwd` to `working_dir`: PASS (test_run_sets_cwd_to_working_dir, line 83 in process.py: `kwargs["cwd"] = self.working_dir`)
  - Parser `init` -> `session.started` with `gemini_session_id` and `model`: PASS
  - Parser `message` (assistant, delta=true) -> `message.delta`: PASS
  - Parser `message` (assistant, no delta) -> `message.created`: PASS
  - Parser `message` (role=user) -> empty list: PASS
  - Parser `tool_use` -> `tool.call.started` with `tool_name` and `tool_input`: PASS
  - Parser `tool_result` (success) -> `tool.call.finished` with `result`: PASS
  - Parser `tool_result` (error) -> `tool.call.finished` with "ERROR: " prefix: PASS
  - Parser `tool_result` for `write_file`/`edit_file` -> `file.changed`: PASS
  - Parser `result` -> `session.completed` with `gemini_session_id`, usage stats, models: PASS
  - Malformed JSON -> empty list, no crash: PASS
  - Empty/blank lines -> empty list: PASS
  - All events include `type` and `session_id`: PASS (test_all_events_include_type_and_session_id)
  - Engine implements all 8 EngineAdapter methods: PASS (test_all_protocol_methods_exist)
  - `isinstance(engine, EngineAdapter)` returns True: PASS (test_isinstance_check)
  - `send_message` captures `gemini_session_id` from init: PASS
  - `send_message` uses `--resume` on second call: PASS
  - Auto-retry on crash up to MAX_RETRIES: PASS
  - Pause/resume works: PASS
  - `GET /api/providers` includes gemini with `type="cli"`: PASS (verified in providers.py)
  - Provider `available=true` when CLI found / `available=false` when missing: PASS
  - `_build_engine(config, engine_type="gemini_cli")` returns GeminiCLIEngine: PASS
  - 25+ tests: PASS (49 tests)
  - Ruff clean: PASS
  - Provider count is 6: PASS (test_provider_count_is_six)
- Stateful parser verification: GeminiCLIParser has `_tool_names: dict[str, str]` and `_tool_params: dict[str, dict]` populated on `tool_use`, consumed on `tool_result` for file.changed emission and file_path extraction. Confirmed in parser.py lines 31-32, 124-126, 154, 167-168.
- VERDICT: PASS

### [PM] 2026-03-19 06:45
- Reviewed implementation: 3 new files (gemini_cli_parser.py, gemini_cli_process.py, gemini_cli_engine.py), 1 test file (49 tests), 3 modified files (providers.py, sessions.py, engine/__init__.py)
- Tests verified: `uv run pytest tests/test_gemini_cli_engine.py -v` -- 49 passed, 0 failed (0.78s)
- Stateful parser verified: `_tool_names: dict[str, str]` and `_tool_params: dict[str, dict]` at parser.py lines 31-32, populated on `tool_use` (lines 124-126), consumed on `tool_result` for tool name lookup (line 154) and file.changed file_path extraction (lines 167-168)
- Code quality: clean, follows established CLI engine patterns (matches copilot_cli_engine structure), proper async generators, good error handling
- All 29 acceptance criteria: MET
  - Parser: all 16 event mapping criteria verified in code and tests
  - Process: command building, cwd, resume all correct
  - Engine: protocol compliance, session management, retry logic, pause/resume all working
  - Integration: provider detection (count=6), engine wiring confirmed
- No scope dropped, no follow-up issues needed
- VERDICT: ACCEPT
