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

## Log

### [SWE] 2026-03-19 12:00
- Confirmed 3 of 4 integration tests FAIL before fix (test_basic_chat, test_event_types_received, test_session_resume)
- Root cause: `_extract_text_content()` in `claude_code_parser.py` had two gaps:
  1. `assistant` events from real CLI have `message` as a nested dict `{"content": [{"type": "text", "text": "..."}]}` — the function received the dict but only handled `str` and `list`, not `dict`
  2. `result` events from real CLI carry final text in a top-level `result` string field — the function never checked it
- Fix: Updated `_extract_text_content()` to (a) check `data.get("result")` for a string first, and (b) recurse into dict values by extracting `.get("content")` when content is a dict
- Files modified: `backend/codehive/engine/claude_code_parser.py`
- Integration tests: 4 passed, 0 failed (all 3 previously failing tests now pass)
- Unit tests: 55 passed, 0 failed (no regressions)
- Ruff: clean, format: clean
