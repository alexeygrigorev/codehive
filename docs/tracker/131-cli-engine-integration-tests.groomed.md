# Issue #131: Real integration tests for CLI engines

## Problem

All CLI engine tests use mocked subprocesses. We have no proof that the actual `claude`, `codex`, `copilot`, or `gemini` CLIs work with our engine implementations. The parsers may not handle real output correctly, the process management may fail in practice, and the session resume may not work.

## Scope

Write integration tests that invoke real CLI binaries with simple prompts and verify our engine + parser stack handles the real output correctly. Tests live in `backend/tests_integration/`, separate from unit tests. This is NOT about testing the CLIs themselves -- it is about testing that our Process + Parser + Engine code works against real CLI output.

## Dependencies

- #09 (engine-adapter-interface) -- DONE
- #33 (claude-code-cli-wrapper) -- DONE
- #34 (claude-code-engine-adapter) -- DONE
- #84 (provider-configuration) -- DONE

No blocking dependencies. Issue #130 (subsessions) lists this as a prerequisite, not the other way around.

## User Stories

Since this is a test-only issue (no UI), user stories describe the developer experience.

### Story: Developer runs Claude integration tests locally
1. Developer has `claude` CLI installed and authenticated
2. Developer runs `cd backend && uv run pytest tests_integration/test_claude_integration.py -v`
3. Test sends "Reply with exactly: hello world" to real Claude CLI via `ClaudeCodeProcess`
4. Test collects all stdout lines and parses them with `ClaudeCodeParser`
5. Test verifies at least one `message.created` event with non-empty content
6. Test verifies a `session.started` event was emitted with a `claude_session_id`
7. All tests pass, output shows real event types received

### Story: Developer runs Codex integration tests locally
1. Developer has `codex` CLI installed and authenticated
2. Developer runs `cd backend && uv run pytest tests_integration/test_codex_integration.py -v`
3. Test sends "Reply with exactly: hello world" to real Codex CLI via `CodexCLIProcess`
4. Test collects all stdout lines and parses them with `CodexCLIParser`
5. Test verifies at least one `message.created` event with non-empty content
6. All tests pass

### Story: Developer runs Copilot integration tests locally
1. Developer has `copilot` (GitHub Copilot CLI) installed and authenticated
2. Developer runs `cd backend && uv run pytest tests_integration/test_copilot_integration.py -v`
3. Test sends a simple prompt to real Copilot CLI via `CopilotCLIProcess`
4. Test collects all stdout lines and parses them with `CopilotCLIParser`
5. Test verifies at least one `message.created` event with non-empty content
6. All tests pass

### Story: Developer runs Gemini integration tests locally
1. Developer has `gemini` CLI installed and authenticated
2. Developer runs `cd backend && uv run pytest tests_integration/test_gemini_integration.py -v`
3. Test sends a simple prompt to real Gemini CLI via `GeminiCLIProcess`
4. Test collects all stdout lines and parses them with `GeminiCLIParser`
5. Test verifies at least one `message.created` event with non-empty content
6. Test verifies a `session.started` event was emitted with a `gemini_session_id`
7. All tests pass

### Story: Developer runs all integration tests at once
1. Developer runs `cd backend && uv run pytest tests_integration/ -v`
2. Tests for engines whose CLI is not installed are marked `xfail` with reason "CLI not found"
3. Tests for engines whose CLI is installed run and pass
4. Output clearly shows which engines were tested and which were skipped

### Story: Developer runs session resume integration test
1. Developer has `claude` CLI installed
2. Developer runs `cd backend && uv run pytest tests_integration/test_claude_integration.py::TestClaudeIntegration::test_session_resume -v`
3. Test sends a first message, captures the `claude_session_id` from the `session.started` event
4. Test sends a second message with `--resume <session_id>`
5. Test verifies the second invocation also produces events (does not crash)
6. Test passes

## Structure

```
backend/tests_integration/
    __init__.py
    conftest.py                          # Shared fixtures: require_cli, tmp working dir, event collector
    test_claude_integration.py           # Claude Code CLI tests
    test_codex_integration.py            # Codex CLI tests
    test_copilot_integration.py          # Copilot CLI tests
    test_gemini_integration.py           # Gemini CLI tests
```

### Shared fixtures (conftest.py)

- `require_cli(name)` -- check `shutil.which(name)`, if not found mark test `xfail(reason="CLI {name} not found on PATH")`
- `tmp_workdir` -- a temporary directory for the CLI to use as working dir (avoid side effects on the real repo)
- `collect_events(async_iter)` -- async helper to drain an async iterator into a list

### Per-engine test file pattern

Each file follows the same structure:

```python
@pytest.fixture(autouse=True)
def _require_engine_cli():
    require_cli("claude")  # or codex, copilot, gemini

class TestClaudeIntegration:
    async def test_basic_chat(self, tmp_workdir):
        """Send a simple prompt, verify we get a message.created event."""

    async def test_event_types_received(self, tmp_workdir):
        """Send a prompt, collect all events, verify the event types we expect."""

    async def test_session_resume(self, tmp_workdir):
        """Send msg1, capture session_id, send msg2 with --resume, verify success."""

    async def test_error_handling(self, tmp_workdir):
        """Invoke with invalid flags, verify graceful error (no crash, no hang)."""
```

## Acceptance Criteria

- [ ] Directory `backend/tests_integration/` exists with `__init__.py` and `conftest.py`
- [ ] `conftest.py` has `require_cli` fixture that marks tests `xfail` when CLI is not on PATH
- [ ] `conftest.py` has `tmp_workdir` fixture providing a temporary working directory
- [ ] `test_claude_integration.py` has at least 4 tests: basic_chat, event_types, session_resume, error_handling
- [ ] `test_codex_integration.py` has at least 3 tests: basic_chat, event_types, error_handling
- [ ] `test_copilot_integration.py` has at least 3 tests: basic_chat, event_types, error_handling
- [ ] `test_gemini_integration.py` has at least 4 tests: basic_chat, event_types, session_resume, error_handling
- [ ] Each `basic_chat` test sends a deterministic prompt (e.g. "Reply with exactly: hello world") via the real Process class and parses output with the real Parser class
- [ ] Each `basic_chat` test asserts at least one `message.created` event with non-empty `content`
- [ ] Each `event_types` test collects all events from a real run and asserts the types include at least `message.created` (and `session.started` for claude/gemini)
- [ ] Claude and Gemini `session_resume` tests: send message 1, capture session ID from `session.started`, send message 2 with `resume_session_id`, verify events received from second call
- [ ] Each `error_handling` test invokes the process with invalid arguments and verifies either a proper error event or an exception (not a hang, not a crash with traceback)
- [ ] Tests use the real Process and Parser classes from `codehive.engine.*`, NOT mocked versions
- [ ] Tests are NOT in the regular `backend/tests/` directory -- they are in `backend/tests_integration/`
- [ ] `cd backend && uv run pytest tests_integration/ -v` runs without import errors (even if all CLIs are missing -- tests just xfail)
- [ ] `cd backend && uv run pytest tests/ -v` still passes (integration tests not mixed in)
- [ ] Each test has a timeout (use `@pytest.mark.timeout(120)` or similar) so tests cannot hang indefinitely
- [ ] Ruff clean: `cd backend && uv run ruff check tests_integration/`

## Test Scenarios

### Unit: conftest fixtures
- `require_cli("nonexistent_tool_xyz")` marks test as xfail
- `require_cli("python")` does NOT mark test as xfail (python is always available)
- `tmp_workdir` provides a real temporary path that exists

### Integration: Claude engine (requires `claude` CLI)
- **basic_chat**: `ClaudeCodeProcess.run("Reply with exactly: hello world")` yields JSONL lines; `ClaudeCodeParser.parse_line()` produces `message.created` events
- **event_types**: Full run produces `session.started` with non-empty `claude_session_id` and at least one `message.created`
- **session_resume**: First run captures `claude_session_id`; second run with `resume_session_id=<id>` succeeds and produces events
- **error_handling**: `ClaudeCodeProcess.run()` with `extra_flags=["--nonexistent-flag"]` raises `ClaudeProcessError` or yields an error event within timeout

### Integration: Codex engine (requires `codex` CLI)
- **basic_chat**: `CodexCLIProcess` with prompt yields JSONL lines; `CodexCLIParser.parse_line()` produces events including `message.created`
- **event_types**: Full run produces recognizable event types
- **error_handling**: Invalid invocation handled gracefully

### Integration: Copilot engine (requires `copilot` CLI)
- **basic_chat**: `CopilotCLIProcess.run()` with prompt yields lines; `CopilotCLIParser.parse_line()` produces events including `message.created`
- **event_types**: Full run produces recognizable event types
- **error_handling**: Invalid invocation handled gracefully

### Integration: Gemini engine (requires `gemini` CLI)
- **basic_chat**: `GeminiCLIProcess.run()` with prompt yields lines; `GeminiCLIParser.parse_line()` produces `message.created` events
- **event_types**: Full run produces `session.started` with `gemini_session_id`
- **session_resume**: First run captures `gemini_session_id`; second run with `resume_session_id=<id>` succeeds
- **error_handling**: Invalid invocation handled gracefully

### Structural
- `uv run pytest tests_integration/ --collect-only` collects at least 14 tests (4 claude + 3 codex + 3 copilot + 4 gemini)
- `uv run pytest tests/ -v` passes unchanged (no regressions)
- `uv run ruff check tests_integration/` is clean

## Notes

- These tests make real LLM API calls -- they are slow and cost money. They should NEVER be in CI.
- Use simple deterministic prompts ("Reply with exactly: hello world") to minimize token usage and make assertions reliable.
- Codex does not support `--resume` (it uses `codex exec` which is non-interactive), so no session_resume test for codex.
- Copilot captures session ID from the `result` event (not `init`), which may not always be present for simple prompts. Resume test is optional for copilot -- only add if the session ID capture works reliably.
- The `xfail` approach (not `skip`) is intentional: missing CLIs show as expected failures in the report, making it visible which engines were not tested. Tests that were expected to fail but actually passed will show as `XPASS`, alerting that a CLI became available.
- Timeout of 120 seconds per test is generous but necessary -- LLM calls can be slow.
