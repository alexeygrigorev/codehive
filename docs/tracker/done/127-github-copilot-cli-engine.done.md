# Issue #127: Add GitHub Copilot CLI as an engine option

## Summary

Add GitHub Copilot CLI (`copilot`) as a third CLI-based engine in codehive, following the same trio pattern as ClaudeCodeEngine (#121) and CodexCLIEngine (#111). The Copilot CLI v1.0.9 is installed and fully supports non-interactive mode with JSON output, session resume, and auto-approval -- all capabilities required for integration.

## Research Findings (PM grooming, 2026-03-19)

### CLI Location and Version

```
$ which copilot
/home/alexey/.nvm/versions/node/v24.13.1/bin/copilot

$ copilot --version
GitHub Copilot CLI 1.0.9.
```

The `copilot` binary is a standalone CLI (NOT `gh copilot` -- it is a separate Node.js package). Detection uses `shutil.which("copilot")`.

### JSON Output Format (--output-format json)

The CLI emits JSONL (one JSON object per line). Each event has this structure:

```json
{
  "type": "<event_type>",
  "data": { ... },
  "id": "<uuid>",
  "timestamp": "<ISO 8601>",
  "parentId": "<uuid>",
  "ephemeral": true|false  // optional, present on streaming/transient events
}
```

### Copilot Event Types -> Codehive Event Mapping

| Copilot Event Type | Description | Codehive Event |
|---|---|---|
| `session.mcp_server_status_changed` | MCP server connected | (skip, ephemeral) |
| `session.mcp_servers_loaded` | MCP servers ready | (skip, ephemeral) |
| `session.tools_updated` | Model and tools ready; `data.model` has model name | `session.started` (capture model) |
| `user.message` | Echo of user prompt | (skip) |
| `assistant.turn_start` | Turn begins; `data.turnId`, `data.interactionId` | (skip, internal) |
| `assistant.reasoning_delta` | Streaming reasoning chunk; `data.deltaContent` | (skip, ephemeral) |
| `assistant.reasoning` | Full reasoning text | (skip, ephemeral) |
| `assistant.message_delta` | Streaming text chunk; `data.messageId`, `data.deltaContent` | `message.delta` |
| `assistant.message` | Complete message; `data.content`, `data.toolRequests[]` | `message.created` |
| `tool.execution_start` | Tool call begins; `data.toolCallId`, `data.toolName`, `data.arguments` | `tool.call.started` |
| `tool.execution_complete` | Tool call done; `data.toolCallId`, `data.success`, `data.result` | `tool.call.finished` |
| `assistant.turn_end` | Turn completed | (skip, internal) |
| `session.background_tasks_changed` | Background tasks updated | (skip, ephemeral) |
| `result` | Final result; `sessionId`, `exitCode`, `usage{}` | `session.completed` (captures session ID + usage) |

### Session ID and Resume

The `result` event (last line of output) contains `"sessionId": "<uuid>"`. This is the session ID used for `--resume=<sessionId>`. Resume is confirmed working -- the CLI remembers conversation history across invocations.

### Tool Call Format

Tool calls arrive in `assistant.message` events in `data.toolRequests[]`:

```json
{
  "toolCallId": "tooluse_...",
  "name": "bash",
  "arguments": {"command": "ls /tmp", "description": "List files"},
  "type": "function",
  "intentionSummary": "List files in /tmp"
}
```

Tool results arrive in `tool.execution_complete` events:

```json
{
  "toolCallId": "tooluse_...",
  "toolName": "bash",
  "success": true,
  "result": {"content": "...", "detailedContent": "..."}
}
```

### Key CLI Flags for Codehive Integration

```
copilot -p "<prompt>" \
  --output-format json \
  --allow-all-tools \
  --autopilot \
  --no-auto-update \
  --add-dir <project_root>
```

For resume:
```
copilot -p "<prompt>" \
  --resume=<sessionId> \
  --output-format json \
  --allow-all-tools \
  --no-auto-update
```

### Auth

Uses GitHub authentication. No API key needed -- authenticated via `gh auth` / GitHub token.

## Dependencies

- #111 (CodexCLIEngine) -- `.done.md` -- pattern to follow
- #121 (ClaudeCodeEngine refactor) -- `.done.md` -- pattern to follow

## Scope

### In Scope

1. `CopilotCLIProcess` -- subprocess manager for `copilot -p` invocations
2. `CopilotCLIParser` -- JSONL parser mapping Copilot events to codehive events
3. `CopilotCLIEngine` -- EngineAdapter implementation with session resume and auto-retry
4. Provider detection -- add "copilot" to `/api/providers` endpoint
5. Engine registration in `__init__.py`
6. Unit tests for all three classes
7. Provider endpoint test update (5 providers instead of 4)

### Out of Scope

- Web UI changes (provider dropdown already handles dynamic provider list)
- MCP server configuration passthrough
- Model selection (uses default; future issue)

## Files to Create/Modify

### New Files
- `backend/codehive/engine/copilot_cli_process.py` -- CopilotCLIProcess
- `backend/codehive/engine/copilot_cli_parser.py` -- CopilotCLIParser
- `backend/codehive/engine/copilot_cli_engine.py` -- CopilotCLIEngine
- `backend/tests/test_copilot_cli_engine.py` -- All unit tests

### Modified Files
- `backend/codehive/engine/__init__.py` -- Add CopilotCLIEngine to exports
- `backend/codehive/api/routes/providers.py` -- Add copilot detection
- `backend/tests/test_providers_endpoint.py` -- Update expected provider count (4 -> 5)

## Acceptance Criteria

- [ ] `shutil.which("copilot")` detection: copilot appears in `GET /api/providers` when CLI is on PATH, absent when not
- [ ] `CopilotCLIProcess._build_command()` produces correct CLI args: `copilot -p <msg> --output-format json --allow-all-tools --autopilot --no-auto-update`
- [ ] `CopilotCLIProcess._build_command()` adds `--resume=<id>` when a session ID is provided
- [ ] `CopilotCLIProcess._build_command()` adds `--add-dir <dir>` when working_dir is set
- [ ] `CopilotCLIParser.parse_line()` converts `assistant.message_delta` to `message.delta`
- [ ] `CopilotCLIParser.parse_line()` converts `assistant.message` to `message.created`
- [ ] `CopilotCLIParser.parse_line()` converts `tool.execution_start` to `tool.call.started`
- [ ] `CopilotCLIParser.parse_line()` converts `tool.execution_complete` to `tool.call.finished`
- [ ] `CopilotCLIParser.parse_line()` converts `session.tools_updated` to `session.started` with model name
- [ ] `CopilotCLIParser.parse_line()` converts `result` to `session.completed` with sessionId and usage
- [ ] `CopilotCLIParser.parse_line()` skips ephemeral events (mcp_servers_loaded, reasoning_delta, etc.)
- [ ] `CopilotCLIParser.parse_line()` handles malformed JSON gracefully (returns empty list)
- [ ] `CopilotCLIEngine` implements `EngineAdapter` protocol (isinstance check passes)
- [ ] `CopilotCLIEngine.create_session()` initializes session state
- [ ] `CopilotCLIEngine.send_message()` spawns process, reads lines, yields parsed events
- [ ] `CopilotCLIEngine.send_message()` captures `copilot_session_id` from `result` event for future `--resume`
- [ ] `CopilotCLIEngine.send_message()` second call uses `--resume=<sessionId>`
- [ ] `CopilotCLIEngine` auto-retries on crash (non-zero exit) up to MAX_RETRIES using `--resume`
- [ ] `CopilotCLIEngine.pause()` / `resume()` set/clear pause flag
- [ ] `uv run pytest tests/test_copilot_cli_engine.py -v` passes with 15+ tests
- [ ] `uv run pytest tests/ -v` full suite still passes
- [ ] `uv run ruff check` clean

## Test Scenarios

### Unit: CopilotCLIParser

1. **Parse assistant.message_delta** -- input: `{"type":"assistant.message_delta","data":{"messageId":"abc","deltaContent":"hello"}}` -> output: `[{"type":"message.delta","role":"assistant","content":"hello","session_id":"..."}]`
2. **Parse assistant.message** -- input with `data.content` set -> output: `message.created` event
3. **Parse assistant.message with toolRequests** -- input with `data.toolRequests` array -> output: `message.created` (tool calls handled by separate tool.execution_start events)
4. **Parse tool.execution_start** -- input: `{"type":"tool.execution_start","data":{"toolCallId":"x","toolName":"bash","arguments":{"command":"ls"}}}` -> output: `tool.call.started` event with tool_name and tool_input
5. **Parse tool.execution_complete** -- success case -> `tool.call.finished` with result content
6. **Parse tool.execution_complete** -- failure case (success=false) -> `tool.call.finished` with error
7. **Parse tool.execution_complete for file-editing tool** -- `data.toolName` is "write" or "edit" -> emit both `tool.call.finished` and `file.changed`
8. **Parse session.tools_updated** -> `session.started` with model from `data.model`
9. **Parse result** -> `session.completed` with sessionId and usage data
10. **Skip ephemeral events** -- `session.mcp_servers_loaded`, `assistant.reasoning_delta`, `session.background_tasks_changed` -> empty list
11. **Skip user.message** -> empty list
12. **Malformed JSON** -> empty list, no crash
13. **Empty line** -> empty list
14. **Non-dict JSON** -> empty list

### Unit: CopilotCLIProcess

15. **Build command -- basic** -- verify command list includes `copilot`, `-p`, `--output-format json`, `--allow-all-tools`, `--autopilot`, `--no-auto-update`
16. **Build command -- with resume** -- verify `--resume=<sessionId>` is included
17. **Build command -- with working_dir** -- verify `--add-dir <dir>` is included
18. **Build command -- with extra_flags** -- verify extra flags appended
19. **Spawn and read stdout** -- mock subprocess, verify lines read correctly
20. **Handle process crash** -- non-zero exit code detected via check_for_crash
21. **Stop process** -- SIGTERM then SIGKILL on timeout

### Unit: CopilotCLIEngine

22. **Implements EngineAdapter** -- `isinstance(engine, EngineAdapter)` is True
23. **create_session initializes state** -- session_id tracked in _sessions dict
24. **send_message spawns process and yields events** -- mock process with JSON lines, verify events yielded
25. **send_message captures session ID from result event** -- after first message, session state has copilot_session_id
26. **send_message uses --resume on second call** -- verify resume_session_id passed to process
27. **send_message handles crash with auto-retry** -- process crashes, engine retries with --resume
28. **send_message all retries exhausted** -- yields session.failed event
29. **pause/resume** -- paused session yields session.paused, resume clears flag
30. **cleanup_session removes state** -- session_id no longer in _sessions

### Integration: Provider Detection

31. **Copilot in provider list when available** -- mock `shutil.which("copilot")` returning path -> provider listed with `available: true`
32. **Copilot not in provider list when missing** -- mock returning None -> provider listed with `available: false`
33. **Provider count is 5** -- claude, codex, openai, zai, copilot

## Implementation Notes

### CopilotCLIProcess

Follow `ClaudeCodeProcess` pattern (fire-and-forget per invocation), NOT `CodexCLIProcess` pattern (which manages its own process object). The Copilot CLI, like Claude Code CLI, runs to completion and emits a stream of JSONL on stdout.

Key differences from ClaudeCodeProcess:
- CLI binary: `copilot` not `claude`
- Output format flag: `--output-format json` not `--output-format stream-json`
- Resume flag: `--resume=<id>` (equals sign) not `--resume <id>` (space)
- Working dir: `--add-dir <dir>` not inherited from cwd
- Auto-approve: `--allow-all-tools` (same as claude)
- Additional: `--autopilot` for auto-continuation, `--no-auto-update` to prevent update checks

### CopilotCLIParser

The event format is different from both Claude Code and Codex CLI. Key structural difference: Copilot nests all event data under a `data` key, while Claude Code puts fields at the top level.

```python
# Claude Code: {"type": "assistant", "content": "hello"}
# Copilot:     {"type": "assistant.message", "data": {"content": "hello"}}
```

The session ID comes from the `result` event (last line), not from a `system.init` event like Claude Code.

### CopilotCLIEngine

Same structure as ClaudeCodeEngine:
- `_SessionState` tracks `copilot_session_id` (captured from `result` event)
- First message: no `--resume`
- Subsequent messages: `--resume=<copilot_session_id>`
- Auto-retry on crash with `--resume`

## Log

### [PM] 2026-03-19 04:40 Grooming

- Verified `copilot` CLI is installed at v1.0.9 as a standalone binary (not `gh copilot`)
- Ran `copilot -p "say hello" --output-format json --allow-all-tools` and captured full JSONL output
- Ran tool-using prompt and captured tool.execution_start / tool.execution_complete event format
- Tested session resume with `--resume=<sessionId>` -- confirmed working (remembered previous conversation)
- Mapped all Copilot event types to codehive event format (12 event types identified, 6 mapped, 6 skipped)
- Previous PM deferral was WRONG -- all required capabilities are present and documented
- Created concrete acceptance criteria (21 items) and test scenarios (33 tests)
- Follows trio pattern: CopilotCLIProcess, CopilotCLIParser, CopilotCLIEngine

### [SWE] 2026-03-19 05:58
- Implemented CopilotCLIProcess, CopilotCLIParser, CopilotCLIEngine following ClaudeCodeEngine pattern
- CopilotCLIProcess: fire-and-forget subprocess with --output-format json, --allow-all-tools, --autopilot, --no-auto-update, --resume=<id>, --add-dir <dir>
- CopilotCLIParser: maps 6 Copilot event types to codehive events, skips 8 ephemeral/internal types, handles malformed JSON gracefully
- CopilotCLIEngine: full EngineAdapter implementation with session resume via result event sessionId, auto-retry on crash (MAX_RETRIES=3)
- Registered copilot as 5th provider in /api/providers endpoint (CLI-based, detected via shutil.which)
- Added copilot_cli engine type in _build_engine session routing
- Updated engine/__init__.py exports
- Files created: backend/codehive/engine/copilot_cli_process.py, copilot_cli_parser.py, copilot_cli_engine.py, backend/tests/test_copilot_cli_engine.py
- Files modified: backend/codehive/engine/__init__.py, backend/codehive/api/routes/providers.py, backend/codehive/api/routes/sessions.py, backend/tests/test_providers_endpoint.py
- Tests added: 50 tests covering parser (17), process (9), engine (21), provider detection (3)
- Build results: 50/50 copilot tests pass, 2007/2009 full suite pass (2 pre-existing failures in test_cli.py unrelated to this change), ruff clean, tsc clean, 681/681 web tests pass
- Known limitations: none

### [QA] 2026-03-19 06:15
- Tests (copilot-specific): 50 passed, 0 failed (`uv run pytest tests/test_copilot_cli_engine.py -v`)
- Tests (full backend): 2007 passed, 2 failed (pre-existing in test_cli.py, confirmed by running on stashed clean state), 3 skipped
- Ruff check: clean ("All checks passed!")
- Ruff format: clean ("263 files already formatted")
- Code review: type hints present, follows ClaudeCodeEngine pattern, proper error handling, no hardcoded values
- Acceptance criteria:
  - [x] `shutil.which("copilot")` detection in GET /api/providers: PASS (verified in providers.py and test)
  - [x] `_build_command()` correct CLI args: PASS (test_build_command_basic)
  - [x] `_build_command()` adds `--resume=<id>`: PASS (test_build_command_with_resume)
  - [x] `_build_command()` adds `--add-dir <dir>`: PASS (test_build_command_with_working_dir)
  - [x] Parser: assistant.message_delta -> message.delta: PASS
  - [x] Parser: assistant.message -> message.created: PASS
  - [x] Parser: tool.execution_start -> tool.call.started: PASS
  - [x] Parser: tool.execution_complete -> tool.call.finished: PASS
  - [x] Parser: session.tools_updated -> session.started with model: PASS
  - [x] Parser: result -> session.completed with sessionId and usage: PASS
  - [x] Parser: skips ephemeral events: PASS (7 ephemeral types tested)
  - [x] Parser: malformed JSON returns empty list: PASS
  - [x] Engine: implements EngineAdapter protocol: PASS (isinstance check)
  - [x] Engine: create_session initializes state: PASS
  - [x] Engine: send_message spawns process, yields events: PASS
  - [x] Engine: captures copilot_session_id from result event: PASS
  - [x] Engine: second call uses --resume: PASS (verified via mock call args)
  - [x] Engine: auto-retries on crash with --resume: PASS
  - [x] Engine: pause/resume set/clear flag: PASS
  - [x] 50 tests (15+ required): PASS
  - [x] Full suite passes: PASS (2 pre-existing failures only)
  - [x] Ruff clean: PASS
- Provider endpoint includes copilot: PASS (grep confirmed)
- Engine wiring in sessions.py: PASS (copilot_cli engine type routed)
- VERDICT: PASS

### [PM] 2026-03-19 06:30 Acceptance Review
- Reviewed QA evidence: all 21 acceptance criteria addressed with specific test references
- Ran `uv run pytest tests/test_copilot_cli_engine.py -v`: 49 passed, 1 FAILED
- Failing test: `test_provider_count_is_five` -- asserts `len(result) == 5` but codebase now has 6 providers (gemini was added by a concurrent issue)
- Root cause: test hardcodes provider count as 5, but providers.py now includes claude, codex, openai, zai, copilot, gemini = 6
- This is in the copilot test file itself (test_copilot_cli_engine.py line 960), so it is issue #127's responsibility to fix
- Acceptance criterion "uv run pytest tests/test_copilot_cli_engine.py -v passes" is NOT MET (49/50)
- Acceptance criterion "full suite still passes" is NOT MET due to this same failure
- All other 19 acceptance criteria: MET per QA evidence and confirmed by test output
- VERDICT: REJECT
- Required fix: Update `test_provider_count_is_five` to expect 6 providers (add gemini to docstring and assertion). This is a one-line fix: change `assert len(result) == 5` to `assert len(result) == 6` and update the docstring.
