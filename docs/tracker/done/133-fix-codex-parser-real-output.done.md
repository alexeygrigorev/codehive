# Issue #133: Fix CodexCLIParser for real CLI output

## Problem

Integration tests (#131) revealed that CodexCLIParser doesn't recognize several event types from real `codex exec --json` output:

- `item.completed` — not handled
- `thread.started` — not handled
- `turn.started` — not handled
- `turn.completed` — not handled

## Requirements

- [ ] Add handling for `item.completed`, `thread.started`, `turn.started`, `turn.completed` event types
- [ ] Integration tests for Codex must pass: `cd backend && uv run pytest tests_integration/test_codex_integration.py -v`
- [ ] Existing unit tests must still pass

## Notes

- This is a TDD bug fix — the failing integration tests ARE the reproducing tests
- Run them before fixing to confirm they fail, then fix, then confirm they pass

## Log

### [SWE] 2026-03-19 10:00

**Root causes identified:**
1. `CodexCLIParser` did not handle `item.completed`, `thread.started`, `turn.started`, `turn.completed`, or `turn.failed` event types from real `codex exec --json` output
2. `CodexCLIProcess` did not pass `--skip-git-repo-check`, causing codex to fail silently when the working directory is not a git repo (integration tests use tmp dirs)
3. `CodexCLIProcess` defaulted to model `codex-mini-latest` which is not available in all configurations; changed default to `None` (let codex use its own default)

**BEFORE fix:** 2 integration tests FAILED (0 raw lines received from codex, 0 events parsed)
**AFTER fix:** 3 integration tests PASSED, 49 unit tests PASSED, ruff clean

**Implementation:**
- Added parser handlers for `item.completed` (maps `agent_message` to `message.created`, `error` to `session.error`)
- Added parser handlers for `thread.started` (maps to `session.started`)
- Added parser handlers for `turn.started` and `turn.completed` (pass-through with usage data)
- Added parser handler for `turn.failed` (maps to `session.error`)
- Added `--skip-git-repo-check` to process command builder
- Changed default model from `"codex-mini-latest"` to `None`

**Files modified:**
- `backend/codehive/engine/codex_cli_parser.py` — added 5 new event type handlers
- `backend/codehive/engine/codex_cli_process.py` — added `--skip-git-repo-check` flag, changed default model

**Tests:** 3 integration tests pass, 49 unit tests pass, ruff clean
**Known limitations:** None
