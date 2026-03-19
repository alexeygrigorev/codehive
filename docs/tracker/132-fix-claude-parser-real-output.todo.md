# Issue #132: Fix ClaudeCodeParser for real CLI output

## Problem

Integration tests (#131) revealed that ClaudeCodeParser doesn't handle real `claude` CLI output correctly:

1. `assistant` events: the `message` field is a nested dict, not a string — parser doesn't extract text content
2. `result` events: has a `result` string field the parser doesn't check — final response text is lost

## Requirements

- [ ] Fix parser to extract text from nested `assistant` event format
- [ ] Fix parser to extract text from `result` event's `result` field
- [ ] Integration tests for Claude must pass: `cd backend && uv run pytest tests_integration/test_claude_integration.py -v`
- [ ] Existing unit tests must still pass

## Notes

- This is a TDD bug fix — the failing integration tests ARE the reproducing tests
- Run them before fixing to confirm they fail, then fix, then confirm they pass
