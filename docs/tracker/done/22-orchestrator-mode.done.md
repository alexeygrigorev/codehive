# 22: Orchestrator Mode

## Description
Implement orchestrator mode for sessions. In this mode, the agent plans, decomposes tasks, and spawns sub-agents but does NOT edit files directly. The orchestrator monitors sub-agent progress via events and aggregates their reports to decide next steps.

## Scope
- `backend/codehive/engine/orchestrator.py` -- Orchestrator class: holds orchestrator-specific system prompt, defines the restricted tool set (spawn_subagent + read-only tools only), provides a helper to filter tool definitions, and contains logic for aggregating sub-agent reports into a progress summary
- `backend/codehive/engine/native.py` -- Extend `send_message` to accept a session mode parameter (or resolve it internally) and use the orchestrator's filtered tool set when mode is "orchestrator"; pass the orchestrator system prompt to the Anthropic API call
- `backend/codehive/core/session.py` -- Add a `get_tools_for_mode(mode: str)` helper (or equivalent) that returns the allowed tool names for a given mode; "orchestrator" mode allows only: `spawn_subagent`, `read_file`, `search_files`, `run_shell` (read-only observation); file-editing tools (`edit_file`, `git_commit`) are excluded
- `backend/tests/test_orchestrator.py` -- Orchestrator mode tests

## Behavior
- When session mode is "orchestrator", file-editing tools (`edit_file`, `git_commit`) are removed from the tool set sent to the Anthropic API
- The orchestrator session receives a system prompt that instructs it to plan, decompose, and delegate via sub-agents rather than coding directly
- The orchestrator can call `spawn_subagent` to create multiple sub-agents in parallel
- The orchestrator can call `read_file` and `search_files` for context gathering, and `run_shell` for observation (e.g., running tests, checking status)
- The orchestrator receives sub-agent completion events (`subagent.report`) and can use the aggregated progress to decide: spawn more sub-agents, fix issues (by spawning a fix agent), or declare the mission complete
- `Orchestrator.aggregate_reports(reports)` takes a list of validated sub-agent reports and returns a summary dict with: total sub-agents, completed/failed/blocked counts, all files changed (merged), all warnings (merged), overall status (all_completed / has_failures / has_blocked)

## Dependencies
- Depends on: #21 (sub-agent spawning) -- done
- Depends on: #09 (engine adapter) -- done

## Acceptance Criteria

- [ ] `backend/codehive/engine/orchestrator.py` exists with an `Orchestrator` class (or module-level constants/functions) that defines:
  - `ORCHESTRATOR_SYSTEM_PROMPT`: a string instructing the agent to plan, decompose tasks, and delegate to sub-agents without editing files directly
  - `ORCHESTRATOR_ALLOWED_TOOLS`: a set/list of tool names allowed in orchestrator mode: `{"spawn_subagent", "read_file", "search_files", "run_shell"}`
  - `filter_tools(tool_definitions)`: a function/method that takes the full `TOOL_DEFINITIONS` list and returns only the tools whose names are in `ORCHESTRATOR_ALLOWED_TOOLS`
  - `aggregate_reports(reports)`: a function/method that takes a list of validated sub-agent report dicts (as returned by `SubAgentManager.collect_report`) and returns a summary dict with keys: `total`, `completed`, `failed`, `blocked`, `files_changed` (deduplicated merged list), `warnings` (merged list), `overall_status` (one of `"all_completed"`, `"has_failures"`, `"has_blocked"`)
- [ ] `filter_tools` correctly removes `edit_file` and `git_commit` from the full tool list, keeping `read_file`, `search_files`, `run_shell`, and `spawn_subagent`
- [ ] `aggregate_reports` handles an empty list of reports and returns zeroed counts with `overall_status = "all_completed"`
- [ ] `aggregate_reports` correctly counts completed/failed/blocked statuses and merges `files_changed` and `warnings` across all reports
- [ ] `NativeEngine.send_message` (or a wrapper method) accepts a `mode` parameter; when `mode == "orchestrator"`, it passes only the filtered tool definitions to the Anthropic API call and prepends the orchestrator system prompt
- [ ] When `mode != "orchestrator"` (or mode is not provided), `send_message` behaves exactly as before (full tool set, no orchestrator prompt) -- no regressions
- [ ] If the LLM somehow returns a tool call for a tool not in the filtered set (e.g., `edit_file`), the engine returns an error result for that tool call (defensive check)
- [ ] `backend/tests/test_orchestrator.py` exists with tests covering all scenarios below
- [ ] `uv run pytest backend/tests/test_orchestrator.py -v` passes with 12+ tests
- [ ] `uv run pytest backend/tests/ -v` continues to pass (no regressions)

## Test Scenarios

### Unit: Orchestrator tool filtering
- Call `filter_tools(TOOL_DEFINITIONS)` where TOOL_DEFINITIONS is the full list from `native.py`. Verify the returned list contains exactly 4 tools: `spawn_subagent`, `read_file`, `search_files`, `run_shell`.
- Verify `edit_file` is NOT in the filtered list.
- Verify `git_commit` is NOT in the filtered list.
- Call `filter_tools` with an empty list. Verify an empty list is returned.

### Unit: Orchestrator system prompt
- Verify `ORCHESTRATOR_SYSTEM_PROMPT` is a non-empty string.
- Verify it contains key phrases related to planning and delegation (e.g., "plan", "sub-agent" or "subagent", "do not edit files" or equivalent).

### Unit: aggregate_reports
- Pass an empty list. Verify result has total=0, completed=0, failed=0, blocked=0, files_changed=[], warnings=[], overall_status="all_completed".
- Pass 3 reports all with status="completed", different files_changed. Verify total=3, completed=3, failed=0, blocked=0, files_changed is the merged deduplicated list, overall_status="all_completed".
- Pass 2 reports: one completed, one failed. Verify total=2, completed=1, failed=1, overall_status="has_failures".
- Pass 2 reports: one completed, one blocked. Verify total=2, completed=1, blocked=1, overall_status="has_blocked".
- Pass 3 reports: one completed, one failed, one blocked. Verify overall_status="has_failures" (failures take priority over blocked).
- Pass reports with overlapping files_changed. Verify files_changed is deduplicated.
- Pass reports with warnings. Verify warnings are merged (concatenated, not deduplicated).

### Unit: NativeEngine with orchestrator mode
- Mock Anthropic client to return a text response (no tool calls). Call `send_message` with `mode="orchestrator"`. Verify the Anthropic API was called with only the filtered tool definitions (4 tools, not 6) and a system prompt containing the orchestrator instructions.
- Mock Anthropic client to return a `spawn_subagent` tool call, then a text response. Call `send_message` with `mode="orchestrator"`. Verify the tool call is executed normally and yields `tool.call.started` and `tool.call.finished` events.
- Mock Anthropic client to return a text response. Call `send_message` without specifying mode (or with `mode="execution"`). Verify the full tool set (6 tools) is passed to the Anthropic API and no orchestrator system prompt is included.

### Unit: Defensive tool rejection
- Mock Anthropic client to return an `edit_file` tool call while in orchestrator mode. Verify the engine returns an error result for that tool call (content contains an error message about the tool not being available in orchestrator mode) and the loop continues.

### Unit: No regressions on default mode
- Run the existing `send_message` test (text-only response, no mode specified). Verify behavior is unchanged.

## Notes
- This issue covers the backend orchestrator logic only. The UI for orchestrator mode (tree view, aggregated progress display) is tracked in #23.
- Issue #45 (agent-modes-backend) covers the broader mode system (Brainstorm, Interview, Planning, Execution, Review). This issue focuses narrowly on the orchestrator mode which is a specialization of the Planning mode concept but with sub-agent spawning. The two issues should be compatible: #45 can later integrate orchestrator as one of the modes in a unified mode registry.

## Log

### [SWE] 2026-03-15 12:00
- Implemented orchestrator mode with module-level constants and functions (not a class, as permitted by AC)
- Created `backend/codehive/engine/orchestrator.py` with:
  - `ORCHESTRATOR_SYSTEM_PROMPT`: instructs agent to plan, decompose, delegate via sub-agents, not edit files
  - `ORCHESTRATOR_ALLOWED_TOOLS`: set of 4 allowed tool names
  - `filter_tools(tool_definitions)`: filters full tool list to orchestrator-allowed subset
  - `aggregate_reports(reports)`: aggregates sub-agent reports with deduped files, merged warnings, priority-based overall_status
- Modified `backend/codehive/engine/native.py`:
  - `send_message` now accepts `mode: str | None = None` parameter
  - When `mode="orchestrator"`: uses filtered tools, passes orchestrator system prompt via `system` kwarg
  - Defensive check: rejects disallowed tool calls (e.g. edit_file) with error result in orchestrator mode
  - Default mode (None) behaves exactly as before -- no regressions
- Note: did NOT modify `backend/codehive/core/session.py` -- the scope item mentioned `get_tools_for_mode` helper but all AC are satisfied via the orchestrator module's constants and the engine's mode parameter. Adding a session-level helper would be over-engineering at this point.
- Files modified: `backend/codehive/engine/orchestrator.py` (new), `backend/codehive/engine/native.py`, `backend/tests/test_orchestrator.py` (new)
- Tests added: 18 tests covering all specified scenarios (tool filtering, system prompt, aggregate_reports, engine integration, defensive rejection, no regressions)
- Build results: 356 tests pass (18 new + 338 existing), 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-15 13:30
- Tests: 356 passed, 0 failed (18 in test_orchestrator.py)
- Ruff check: clean
- Ruff format: clean
- AC 1 (orchestrator.py with constants/functions): PASS
- AC 2 (filter_tools removes edit_file/git_commit, keeps 4 allowed): PASS
- AC 3 (aggregate_reports handles empty list): PASS
- AC 4 (aggregate_reports counts statuses, merges files/warnings): PASS
- AC 5 (send_message mode param, orchestrator uses filtered tools + system prompt): PASS
- AC 6 (default mode unchanged, no regressions): PASS
- AC 7 (defensive rejection of disallowed tool calls): PASS
- AC 8 (test_orchestrator.py covers all scenarios): PASS
- AC 9 (12+ tests pass): PASS (18 tests)
- AC 10 (full test suite passes, no regressions): PASS (356 total)
- VERDICT: PASS

### [PM] 2026-03-15 14:15
- Reviewed diff: 3 files changed (orchestrator.py new 103 lines, native.py +40/-7, test_orchestrator.py new 424 lines)
- Results verified: real data present -- 18/18 tests pass in test_orchestrator.py, 356/356 in full suite, ruff clean
- AC 1 (orchestrator.py with prompt, allowed tools, filter_tools, aggregate_reports): MET
- AC 2 (filter_tools removes edit_file/git_commit, keeps 4 allowed): MET
- AC 3 (aggregate_reports empty list returns zeroed counts): MET
- AC 4 (aggregate_reports counts statuses, merges files deduped, warnings concatenated): MET
- AC 5 (send_message mode param, orchestrator filtered tools + system prompt): MET
- AC 6 (default mode unchanged, no regressions): MET -- 338 existing tests unaffected
- AC 7 (defensive rejection of disallowed tool calls in orchestrator mode): MET
- AC 8 (test_orchestrator.py with all scenarios): MET -- 6 test classes covering all specified scenarios
- AC 9 (12+ tests pass): MET -- 18 tests pass
- AC 10 (full suite passes, no regressions): MET -- 356 passed
- Code quality: clean, follows existing patterns (same mock structure as test_engine.py), no over-engineering
- Note: session.py get_tools_for_mode helper was descoped by SWE as unnecessary -- agree, the orchestrator module constants + engine mode param cover the need. No follow-up needed.
- Follow-up issues created: none
- VERDICT: ACCEPT
