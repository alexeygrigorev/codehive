# Issue #131: Real integration tests for CLI engines

## Problem

All CLI engine tests use mocked subprocesses. We have no proof that the actual `claude`, `codex`, `copilot`, or `gemini` CLIs work with our engine implementations. The parsers may not handle real output correctly, the process management may fail in practice, and the session resume may not work.

## Requirements

- [ ] Integration tests that actually invoke each CLI with a simple prompt
- [ ] Verify real JSONL output is parsed correctly by our parsers
- [ ] Verify session resume works with real session IDs
- [ ] Tests should be skippable when CLI is not installed (but FAIL, not skip, per our process)
- [ ] Run as part of a separate test suite (not unit tests) — e.g., `pytest tests/integration/`

## Test Scenarios

### For each CLI engine (Claude, Codex, Copilot, Gemini):
1. **Basic chat**: Send "say hello" → verify assistant response event received
2. **Event parsing**: Capture all events from a real run → verify our parser handles them all
3. **Session resume**: Send first message → capture session ID → send follow-up with --resume → verify context preserved
4. **Tool use**: Send a prompt that triggers file read → verify tool events parsed correctly
5. **Error handling**: Send with invalid flags → verify error is handled gracefully

### Cross-engine:
6. **Provider detection**: Verify /api/providers returns correct availability for installed CLIs
7. **Engine construction**: Verify _build_engine creates correct engine for each type

## Structure

- Separate folder: `backend/tests_integration/` (not mixed with unit tests)
- Run separately: `cd backend && uv run pytest tests/integration/ -v`
- NOT part of regular CI — too slow, requires real CLI tools and API auth
- Each engine in its own file: `test_claude_integration.py`, `test_codex_integration.py`, etc.

## Reference

- See `~/git/telegram-writing-assistant` for integration test patterns — they test real Claude CLI invocations

## Notes

- These tests will be slow (actual LLM calls) — separate folder, not in regular test suite
- May need API keys/auth for some CLIs
- Can't run them all regularly — they cost money and take time
- This is a prerequisite for subsessions (#130) — we need to know the engines actually work before orchestrating them
