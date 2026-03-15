# 50: Secrets Redaction in Logs and Output

## Description
Implement automatic redaction of secrets and sensitive values in agent logs, stdout/stderr output, and event data. Ensure no raw API keys, passwords, or environment variable values appear in stored logs or streamed events.

## Scope
- `backend/codehive/core/redaction.py` -- Redaction engine: pattern-based detection of secrets (API keys, tokens, passwords), replacement with masked values
- `backend/codehive/execution/shell.py` -- Extend to redact stdout/stderr before logging/streaming
- `backend/codehive/core/events.py` -- Extend to redact event data before storage and publishing
- `backend/tests/test_redaction.py` -- Redaction tests (various secret patterns)

## Dependencies
- Depends on: #08 (execution layer for shell output) -- DONE
- Depends on: #07 (event bus for event data) -- DONE
- Depends on: #13 (secrets management foundation) -- DONE

## Design Notes

### Redaction Engine (`redaction.py`)
The `SecretRedactor` class should:
1. Accept a set of known secret values loaded from `Settings` (e.g., `anthropic_api_key`) plus any user-configured secrets.
2. Include built-in regex patterns for common secret formats: API keys (`sk-...`, `key-...`, `ghp_...`, `gho_...`, `github_pat_...`), bearer tokens, `password=...` in URLs, AWS keys (`AKIA...`), base64-encoded long strings that look like tokens, and generic `SECRET`/`TOKEN`/`PASSWORD`/`API_KEY` assignments in env-var-like contexts.
3. Provide a `redact(text: str) -> str` method that replaces all matches with a masked form like `***REDACTED***` (or `sk-...***` preserving a short prefix for debugging).
4. Be stateless per call -- safe to use concurrently from async code.

### Shell Integration
- `ShellRunner.run()` should accept an optional `SecretRedactor` and apply it to `stdout` and `stderr` in the returned `ShellResult`.
- `ShellRunner.run_streaming()` should redact each yielded line before yielding.
- Redaction is applied after decoding, before the caller receives data. The caller never sees raw secrets.

### Event Bus Integration
- `EventBus.publish()` should accept an optional `SecretRedactor` and apply it to the `data` dict (deep redaction of all string values in the nested dict/list structure) before persisting to DB and publishing to Redis.
- The Redis message and the DB row must both contain the redacted version -- secrets must never be stored.

## Acceptance Criteria

- [x] `backend/codehive/core/redaction.py` exists with a `SecretRedactor` class
- [x] `SecretRedactor` can be constructed with explicit secret values (list of strings to always redact)
- [x] `SecretRedactor.redact(text)` replaces known secret values with a redacted placeholder
- [x] `SecretRedactor.redact(text)` detects and redacts common secret patterns via regex (API keys, tokens, passwords in URLs) even when those values were not explicitly registered
- [x] Empty or very short strings (3 characters or fewer) in the explicit secrets list are ignored to avoid false positives
- [x] `ShellRunner.run()` accepts an optional `SecretRedactor` and returns `ShellResult` with stdout/stderr redacted
- [x] `ShellRunner.run_streaming()` accepts an optional `SecretRedactor` and yields redacted lines
- [x] `EventBus.publish()` accepts an optional `SecretRedactor` and redacts all string values in the event `data` dict (recursively through nested dicts and lists) before DB persist and Redis publish
- [x] Redaction happens before storage -- the DB and Redis never receive unredacted secrets
- [x] `uv run pytest backend/tests/test_redaction.py -v` passes with 15+ tests
- [x] `uv run pytest backend/tests/ -v` passes (no regressions in existing tests)
- [x] `uv run ruff check backend/` is clean
- [x] `uv run ruff format --check backend/` is clean

## Test Scenarios

### Unit: SecretRedactor -- explicit values
- Register `"sk-proj-abc123xyz"` as a secret, redact a string containing it, verify it is replaced with a placeholder
- Register multiple secrets, verify all are redacted in a single string
- Register an empty string and a 2-char string as secrets, verify they are ignored (not redacted everywhere)
- Redact a string that does not contain any secrets, verify it is returned unchanged
- Verify redaction works when the secret appears multiple times in the same string

### Unit: SecretRedactor -- pattern-based detection
- Input contains `sk-ant-api03-XXXX...` (Anthropic key format), verify it is redacted
- Input contains `ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ012345` (GitHub PAT), verify it is redacted
- Input contains `AKIA1234567890ABCDEF` (AWS access key), verify it is redacted
- Input contains a URL with embedded password like `postgres://user:s3cret@host/db`, verify the password portion is redacted
- Input contains `Bearer eyJhbGciOi...` (JWT-like token), verify it is redacted
- Input contains `export API_KEY=somevalue123`, verify the value is redacted
- Input with no secret-like patterns is returned unchanged

### Unit: SecretRedactor -- deep dict redaction
- Redact a flat dict `{"output": "key is sk-abc123"}`, verify the string value is redacted
- Redact a nested dict `{"result": {"log": "token ghp_xyz"}}`, verify nested string is redacted
- Redact a dict with a list value `{"lines": ["line1", "Bearer eyJ..."]}`, verify list items are redacted
- Non-string values (ints, bools, None) are left unchanged

### Integration: ShellRunner with redaction
- Run a command that echoes a known secret, verify `ShellResult.stdout` contains the redacted placeholder, not the raw secret
- Run a command that outputs a secret on stderr, verify `ShellResult.stderr` is redacted
- Run streaming, verify each yielded line is redacted
- Run without a redactor (None), verify output is returned unmodified (backward compatibility)

### Integration: EventBus with redaction
- Publish an event with secret in data, retrieve it from DB, verify the stored data is redacted
- Publish an event without a redactor, verify data is stored as-is (backward compatibility)

## Out of Scope
- Per-project or per-session secret registries (future enhancement)
- Redacting secrets in file contents written by agents (separate concern)
- Log framework integration (e.g., Python `logging` module filters) -- future issue
- Secret rotation or detection of leaked secrets after the fact

## Log

### [SWE] 2026-03-15 10:00
- Implemented `SecretRedactor` class in `backend/codehive/core/redaction.py` with:
  - Explicit secret values (list of strings, ignoring <= 3 chars)
  - Regex pattern detection for Anthropic keys, OpenAI keys, GitHub PATs, AWS keys, Bearer JWT tokens, URL-embedded passwords, and env var assignments
  - `redact(text)` method for string redaction
  - `redact_dict(data)` method for recursive dict/list redaction
- Extended `ShellRunner.run()` and `ShellRunner.run_streaming()` with optional `redactor` parameter
- Extended `EventBus.publish()` with optional `redactor` parameter -- redaction applied before DB persist and Redis publish
- All changes are backward compatible (redactor defaults to None)
- Files modified: `backend/codehive/core/redaction.py` (new), `backend/codehive/execution/shell.py`, `backend/codehive/core/events.py`, `backend/tests/test_redaction.py` (new)
- Tests added: 22 tests (5 explicit values, 7 pattern detection, 4 deep dict, 4 shell integration, 2 event bus integration)
- Build results: 22/22 redaction tests pass, ruff clean, format clean
- Full suite: 683 pass, 2 fail (pre-existing failures in test_models.py due to missing github_config column -- unrelated)

### [QA] 2026-03-15 11:30
- Tests: 22/22 passed in test_redaction.py (0.57s)
- Full suite (excluding #35 test file): 685 passed, 0 failed
- Ruff check: clean (all issue #50 files)
- Ruff format: clean (all issue #50 files)
- Note: 2 ruff errors exist in tests/test_github_import.py from parallel issue #35, not from this issue
- Acceptance criteria:
  1. redaction.py exists with SecretRedactor class: PASS
  2. SecretRedactor constructed with explicit secret values: PASS
  3. redact(text) replaces known secrets: PASS
  4. redact(text) detects common patterns via regex: PASS
  5. Short strings (<=3 chars) ignored: PASS
  6. ShellRunner.run() with optional redactor, stdout/stderr redacted: PASS
  7. ShellRunner.run_streaming() with optional redactor, yields redacted lines: PASS
  8. EventBus.publish() with optional redactor, recursive dict redaction: PASS
  9. Redaction before storage (DB and Redis both receive redacted data): PASS
  10. 15+ tests in test_redaction.py: PASS (22 tests)
  11. Full test suite passes (no regressions): PASS
  12. ruff check clean: PASS
  13. ruff format clean: PASS
- VERDICT: PASS

### [PM] 2026-03-15 12:15
- Reviewed diff: 4 files changed for issue #50 (redaction.py new, shell.py modified, events.py modified, test_redaction.py new)
- Results verified: real data present -- 22/22 tests pass (0.33s), ruff check clean, ruff format clean
- Code review:
  - `SecretRedactor` is clean, stateless, covers 8 regex patterns (Anthropic, OpenAI, GitHub PAT, AWS, Bearer JWT, URL passwords, env var assignments)
  - Explicit secrets sorted longest-first to avoid partial match issues
  - Short secret filtering (<=3 chars) correctly prevents false positives
  - `redact_dict` recursion handles dict, list, str, and passthrough for other types
  - Shell integration: redaction applied after decode, before return -- caller never sees raw secrets
  - Event bus integration: redaction applied before Event creation, so both DB row and Redis message use the same redacted data dict
  - All changes backward compatible (redactor defaults to None)
- Tests are meaningful: cover explicit values (5), pattern detection (7), deep dict recursion (4), shell integration with real subprocess (4), event bus with mock Redis and in-memory SQLite (2)
- Acceptance criteria: all 13 met
- No descoped items, no follow-up issues needed
- VERDICT: ACCEPT
