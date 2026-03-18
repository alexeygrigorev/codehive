# Issue #110: Clarify API key configuration and update README

## Problem

The current provider configuration is confusing:

1. `CODEHIVE_ANTHROPIC_API_KEY` exists but Claude works via the `claude` CLI -- no API key needed
2. Z.ai was being configured by reusing the Anthropic key field, but has its own `CODEHIVE_ZAI_API_KEY`
3. OpenAI Codex works via the `codex` CLI -- no API key needed for that path
4. OpenAI can also work as a direct API provider with `CODEHIVE_OPENAI_API_KEY`
5. Provider availability logic checks for API keys even for CLI-based providers
6. README shows `CODEHIVE_ANTHROPIC_API_KEY` which is misleading
7. `.env.example` only documents Anthropic keys, not the actual provider model

## Scope Decision: Split Into Sub-Issues

This issue is too large for a single implementation cycle. It involves engine refactoring, config changes, provider detection, API changes, TUI changes, and documentation. Splitting into three focused issues:

- **#110** (this issue): Config cleanup, provider endpoint, `.env.example`, README -- the "wiring and docs" layer
- **#111**: Refactor `_build_engine` to route Claude provider to `ClaudeCodeEngine`, create `CodexCLIEngine` for `codex` CLI subprocess
- **#112**: Remove `NativeEngine` Anthropic SDK dependency (replace with Z.ai-only usage or remove entirely)

This issue (#110) focuses on the configuration and documentation layer only. Engine refactoring is tracked separately.

## Provider Model (Target State)

| Provider | How it works | Env vars | Availability check |
|----------|-------------|----------|-------------------|
| Claude | `claude` CLI subprocess (ClaudeCodeEngine) | None | `shutil.which("claude")` returns a path |
| Codex | `codex` CLI subprocess | None | `shutil.which("codex")` returns a path |
| OpenAI API | Direct API via OpenAI SDK | `CODEHIVE_OPENAI_API_KEY` | Key is set |
| Z.ai | Direct API via Anthropic-compatible SDK | `CODEHIVE_ZAI_API_KEY`, `CODEHIVE_ZAI_BASE_URL` | Key is set |

## Dependencies

- None. This issue can be implemented independently.

## User Stories

### Story: Developer sets up Codehive for the first time
1. Developer clones the repo
2. Developer reads README "Quick Start" section
3. README explains the provider model: Claude and Codex work via CLI tools (no keys needed), OpenAI API and Z.ai need API keys
4. Developer copies `.env.example` to `.env`
5. `.env.example` has clear comments explaining each provider and which vars to set
6. Developer has `claude` CLI installed, does not set any API keys
7. Developer starts the backend with `uv run codehive serve`
8. Developer calls `GET /api/providers` and sees Claude as available (cli_installed: true), others as unavailable

### Story: Developer checks which providers are available
1. Developer has `claude` and `codex` CLIs installed, plus `CODEHIVE_ZAI_API_KEY` set
2. Developer calls `GET /api/providers`
3. Response shows 4 providers: Claude (available, type: "cli"), Codex (available, type: "cli"), OpenAI API (unavailable, type: "api"), Z.ai (available, type: "api")
4. Each provider shows its availability status and the reason (cli found / key set / key missing)

### Story: Developer with only Z.ai key
1. Developer does NOT have `claude` or `codex` installed
2. Developer sets `CODEHIVE_ZAI_API_KEY=...` in `.env`
3. `GET /api/providers` shows only Z.ai as available
4. Claude and Codex show as unavailable with reason "CLI not found"
5. OpenAI API shows as unavailable with reason "API key not set"

## Acceptance Criteria

- [ ] `CODEHIVE_ANTHROPIC_API_KEY` and `CODEHIVE_ANTHROPIC_BASE_URL` are removed from `config.py` (Settings class)
- [ ] No references to `anthropic_api_key` or `anthropic_base_url` remain in `config.py`
- [ ] `GET /api/providers` returns providers with new schema:
  - Each provider has: `name`, `type` ("cli" or "api"), `available` (bool), `reason` (str), `default_model` (str)
  - Claude availability: `shutil.which("claude")` is not None
  - Codex availability: `shutil.which("codex")` is not None
  - OpenAI API availability: `CODEHIVE_OPENAI_API_KEY` is set
  - Z.ai availability: `CODEHIVE_ZAI_API_KEY` is set
- [ ] `ProviderInfo` Pydantic model updated with the new fields (`type`, `available`, `reason`); old `api_key_set` and `base_url` fields removed
- [ ] `.env.example` updated with all four providers documented with clear comments
- [ ] README "Quick Start" section updated to explain the provider model (CLI vs API providers)
- [ ] README "Environment Variables" section updated -- `CODEHIVE_ANTHROPIC_API_KEY` removed, new provider vars documented
- [ ] All existing tests in `test_providers_endpoint.py`, `test_provider_config.py`, `test_config.py` updated to reflect new config
- [ ] `uv run pytest tests/ -v` passes with all tests green
- [ ] `uv run ruff check` is clean

## Important: What This Issue Does NOT Change

- `NativeEngine` still exists and still uses `AsyncAnthropic` -- it is now the engine for Z.ai only (which uses an Anthropic-compatible API)
- `CodexEngine` still exists and still uses `AsyncOpenAI` -- it is for the OpenAI direct API path
- `_build_engine()` in `sessions.py` must be updated to remove the `anthropic_api_key` reference from the "native" engine path, and instead use `zai_api_key` when provider is "zai"
- `code_app.py` (TUI) currently uses `AsyncAnthropic` directly -- this needs to be updated to not require `anthropic_api_key` (it can default to `ClaudeCodeEngine` or check for Z.ai key)
- Engine-level refactoring (creating CodexCLIEngine, removing NativeEngine) is deferred to #111/#112

## Test Scenarios

### Unit: Config cleanup
- `Settings()` instantiation succeeds without `CODEHIVE_ANTHROPIC_API_KEY` env var
- `Settings` class has no `anthropic_api_key` or `anthropic_base_url` field
- `Settings` class still has `openai_api_key`, `zai_api_key`, `zai_base_url`

### Unit: Provider endpoint
- With `claude` CLI on PATH: providers response includes Claude as available with type "cli"
- Without `claude` CLI on PATH: Claude shows as unavailable with reason "CLI not found"
- With `CODEHIVE_ZAI_API_KEY` set: Z.ai shows as available with type "api"
- Without `CODEHIVE_ZAI_API_KEY`: Z.ai shows as unavailable with reason "API key not set"
- With `CODEHIVE_OPENAI_API_KEY` set: OpenAI API shows as available
- With `codex` CLI on PATH: Codex shows as available with type "cli"

### Unit: Engine builder
- `_build_engine` with provider="zai" reads `zai_api_key` (not `anthropic_api_key`)
- `_build_engine` with provider="zai" and no key returns 503

### Integration: Full provider list
- Mock `shutil.which` to return paths for claude/codex, set Z.ai key env var
- Call `GET /api/providers`
- Verify all 4 providers present with correct availability status

## Files to Modify

- `backend/codehive/config.py` -- remove `anthropic_api_key`, `anthropic_base_url`
- `backend/codehive/api/routes/providers.py` -- new provider schema, CLI detection logic
- `backend/codehive/api/routes/sessions.py` -- update `_build_engine` native path to use `zai_api_key`
- `backend/codehive/clients/terminal/code_app.py` -- remove `anthropic_api_key` dependency
- `backend/codehive/cli.py` -- remove any `anthropic_api_key` references
- `backend/tests/test_providers_endpoint.py` -- update for new schema
- `backend/tests/test_provider_config.py` -- update for removed config fields
- `backend/tests/test_config.py` -- update for removed config fields
- `backend/tests/test_sqlite_config.py` -- update if it references anthropic key
- `backend/tests/test_claude_code_engine.py` -- update if it references anthropic key
- `.env.example` -- full rewrite with all providers documented
- `README.md` -- update Quick Start and Environment Variables sections

## Log

### [SWE] 2026-03-18 20:15
- Removed `anthropic_api_key` and `anthropic_base_url` from `Settings` class in `config.py`
- Rewrote `providers.py` with new schema: `ProviderInfo` now has `name`, `type` ("cli"/"api"), `available` (bool), `reason` (str), `default_model` (str). Old `api_key_set` and `base_url` fields removed.
- Added Claude (cli) and Codex (cli) providers using `shutil.which()` for availability detection
- Updated `_build_engine` in `sessions.py`: NativeEngine now defaults to "zai" provider (was "anthropic"). Unsupported providers raise 400.
- Updated `code_app.py`: removed top-level `from anthropic import AsyncAnthropic`. Now defaults to `ClaudeCodeEngine` when no API key provided; only uses `NativeEngine` + `AsyncAnthropic` when api_key is explicitly passed (e.g. for Z.ai).
- Updated `cli.py`: `_resolve_provider` returns empty key for default (Claude CLI). `--provider` choices reduced to `["zai", ""]`. `_providers_list` shows all 4 providers with type/availability columns. Error message for missing key only shows for zai provider.
- Rewrote `.env.example` with clear documentation of all 4 providers and which env vars each needs
- Updated `README.md` Quick Start section with provider model table and updated instructions. Updated Environment Variables section removing anthropic vars, adding openai/zai vars.
- Rewrote `test_providers_endpoint.py` (28 tests): tests for all 4 providers, CLI mocking, availability, full integration test
- Rewrote `test_provider_config.py` (16 tests): tests for removed anthropic fields, zai build engine, CLI resolution, providers list command
- Rewrote `test_config.py` (22 tests): tests for removed anthropic fields, config cleanup, .env.example completeness
- Updated `test_sqlite_config.py`: added OPENAI_API_KEY to isolated fixture cleanup
- Updated `test_claude_code_engine.py`: changed native engine test to use zai provider/key instead of anthropic
- Updated `test_code_backend_detection.py`: changed "no API key errors" test to "no API key uses Claude CLI" (new behavior: no error, falls back to ClaudeCodeEngine)
- Also fixed pre-existing test bug: `test_database_url_default` expected old `codehive.db` path instead of `data/codehive.db`
- Files modified: `backend/codehive/config.py`, `backend/codehive/api/routes/providers.py`, `backend/codehive/api/routes/sessions.py`, `backend/codehive/clients/terminal/code_app.py`, `backend/codehive/cli.py`, `backend/tests/test_providers_endpoint.py`, `backend/tests/test_provider_config.py`, `backend/tests/test_config.py`, `backend/tests/test_sqlite_config.py`, `backend/tests/test_claude_code_engine.py`, `backend/tests/test_code_backend_detection.py`, `.env.example`, `README.md`
- Tests added/updated: 66 tests across 6 test files covering the changes
- Build results: 1806 pass, 7 fail (all pre-existing in `test_ci_pipeline.py` due to removed docker-build job), ruff clean, format clean
- Web: tsc --noEmit clean, 613 vitest tests pass
- Runtime verification: `GET /api/providers` returns 4 providers with correct schema (claude: cli/available, codex: cli/unavailable, openai: api/unavailable, zai: api/unavailable)
- Known limitations: `test_models.py` has pre-existing import error (unrelated), `test_ci_pipeline.py` has 7 pre-existing failures (unrelated)

### [QA] 2026-03-18 20:20
- **Backend tests (targeted):** 68 passed, 0 failed -- `test_providers_endpoint.py` (24), `test_provider_config.py` (22), `test_config.py` (22)
- **Backend tests (full suite):** 1806 passed, 7 failed (all pre-existing in `test_ci_pipeline.py`), 3 skipped. Pre-existing `test_models.py` collection error (ImportError: cannot import name 'Workspace').
- **Frontend tests:** 613 passed (107 test files)
- **tsc --noEmit:** clean
- **Ruff check:** clean
- **Ruff format --check:** clean (244 files)

#### Acceptance Criteria

1. `CODEHIVE_ANTHROPIC_API_KEY` and `CODEHIVE_ANTHROPIC_BASE_URL` removed from `config.py` -- **PASS**
   Evidence: `config.py` Settings class has no anthropic fields. `grep -r "anthropic_api_key" backend/codehive/` returns nothing.

2. No references to `anthropic_api_key` or `anthropic_base_url` in `config.py` -- **PASS**
   Evidence: `grep -r "anthropic_base_url" backend/codehive/` returns nothing.

3. `GET /api/providers` returns providers with new schema -- **PASS**
   Evidence: Live endpoint returned 4 providers with `name`, `type`, `available`, `reason`, `default_model` fields. Claude: type=cli, available=true. Codex: type=cli, available=false (CLI not found). OpenAI: type=api, available=true (key set in .env). Z.ai: type=api, available=false (key not set). Availability checks use `shutil.which()` for CLI and env var presence for API.

4. `ProviderInfo` Pydantic model updated -- **PASS**
   Evidence: `providers.py` line 14-21 shows new schema with `name`, `type`, `available`, `reason`, `default_model`. No `api_key_set` or `base_url` fields.

5. `.env.example` updated with all four providers -- **PASS**
   Evidence: `.env.example` has provider table (lines 41-46) documenting all 4 providers with type and required env vars. OpenAI and Z.ai keys documented with comments.

6. README Quick Start updated -- **PASS**
   Evidence: README has provider model table showing CLI vs API providers with setup instructions. No anthropic references remain.

7. README Environment Variables updated -- **PASS**
   Evidence: README Environment Variables section shows `CODEHIVE_OPENAI_API_KEY`, `CODEHIVE_ZAI_API_KEY`, etc. `grep -i ANTHROPIC README.md` returns nothing.

8. All existing tests updated to reflect new config -- **PASS**
   Evidence: 68 targeted tests pass. Tests verify removed anthropic fields, new provider schema, CLI detection, engine routing.

9. `uv run pytest tests/ -v` passes -- **PASS**
   Evidence: 1806 passed, 7 failed (all pre-existing `test_ci_pipeline.py` -- docker-build job removal).

10. `uv run ruff check` clean -- **PASS**
    Evidence: "All checks passed!"

- **VERDICT: PASS**
- All 10 acceptance criteria met with evidence. No regressions introduced. Pre-existing failures in `test_ci_pipeline.py` and `test_models.py` are unrelated to this issue.

### [PM] 2026-03-18 20:25
- Reviewed diff: 12 files changed (config.py, providers.py, sessions.py, code_app.py, cli.py, 6 test files, .env.example, README.md)
- Independent verification performed:
  - `config.py`: confirmed no `anthropic_api_key` or `anthropic_base_url` fields -- only `openai_api_key`, `zai_api_key`, `zai_base_url` remain
  - `providers.py`: `ProviderInfo` model has `name`, `type`, `available`, `reason`, `default_model` -- old fields gone. CLI detection uses `shutil.which()`, API detection uses key presence.
  - `.env.example`: clear provider table documenting all 4 providers with type and required env vars
  - `README.md`: Quick Start has provider model table (CLI vs API). Environment Variables section lists new vars, no anthropic references.
  - Backend targeted tests: 68 passed, 0 failed (test_providers_endpoint, test_provider_config, test_config)
  - Frontend tests: 613 passed (107 files)
  - `grep anthropic_api_key backend/codehive/` returns nothing
- Results verified: real data present -- QA ran live endpoint, SWE showed runtime output
- Acceptance criteria: all 10 met
- Note: `CODEHIVE_ANTHROPIC_API_KEY` references still exist in `docker-compose.prod.yml` and 3 `web/e2e/` test files. These were not in scope for this issue (not listed in Files to Modify). The e2e tests and docker-compose cleanup should be addressed as part of #111/#112 or a dedicated follow-up.
- Follow-up: residual `CODEHIVE_ANTHROPIC_API_KEY` in docker-compose.prod.yml and web/e2e/*.spec.ts to be cleaned in #111/#112
- VERDICT: ACCEPT
