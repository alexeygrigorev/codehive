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
