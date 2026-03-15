# 13: Secrets Management

## Description
Keep it simple: `.env` file for all secrets, `.gitignore` to prevent committing. Most pieces are already in place, but `config.py` does not actually load from `.env` (missing `env_file` in pydantic-settings model_config), and the Settings class is missing fields for API keys. This issue wires everything up properly.

## Scope
- `backend/codehive/config.py` -- add `env_file` to `model_config` so pydantic-settings reads `.env`; add `anthropic_api_key` and `anthropic_base_url` fields (with `CODEHIVE_` prefix, or a separate section without prefix)
- `.env.example` -- add all secret/config fields with placeholder values, including Anthropic keys
- `.env` -- already gitignored, no changes needed to `.gitignore`
- `.gitignore` -- already ignores `.env` and `.env.*` except `.env.example`; verify, no changes expected
- No encryption, no vault, no DB-stored secrets for now

## Current State (What Already Exists)
- `backend/codehive/config.py` uses `pydantic_settings.BaseSettings` with `env_prefix = "CODEHIVE_"` but does NOT set `env_file` -- so `.env` is never loaded
- `.env` exists at repo root with `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` (no `CODEHIVE_` prefix)
- `.env.example` exists with Postgres and Redis vars but no Anthropic vars
- `.gitignore` correctly ignores `.env` and `.env.*`, excepts `.env.example`
- Existing tests in `backend/tests/test_config.py` cover defaults and env-var overrides for host/port/debug/database_url/redis_url

## What Needs to Change
1. Add `env_file = ".env"` (with `env_file_encoding = "utf-8"`) to `Settings.model_config` so pydantic-settings loads the `.env` file automatically
2. Add secret fields to `Settings`: `anthropic_api_key` (optional, default empty string) and `anthropic_base_url` (optional, default empty string)
3. Update `.env.example` to include all environment variables the app uses: Postgres, Redis, Anthropic API key, Anthropic base URL, debug, host, port
4. Ensure the `.env` file uses the `CODEHIVE_` prefix for fields consumed by Settings (or configure pydantic-settings to also read un-prefixed vars for secrets -- decide during implementation)

## Decision
Simplest approach: `.env` + `.gitignore`. All secrets accessed via `Settings` class. Revisit if/when multi-user or deployment needs arise.

## Dependencies
- Depends on: `done/01-fastapi-app-setup.done.md` (config.py must exist) -- DONE

## Acceptance Criteria

- [x] `Settings.model_config` includes `env_file` pointing to `.env` so that values are loaded from the file
- [x] `Settings` class has `anthropic_api_key: str` and `anthropic_base_url: str` fields (with sensible defaults for when not set)
- [x] Instantiating `Settings()` in a directory containing a `.env` file picks up values from that file
- [x] Environment variables still override `.env` file values (pydantic-settings default behavior -- just verify)
- [x] `.env.example` contains every variable that `.env` could contain, with placeholder/example values and comments
- [x] `.env.example` includes at minimum: `CODEHIVE_HOST`, `CODEHIVE_PORT`, `CODEHIVE_DEBUG`, `CODEHIVE_DATABASE_URL`, `CODEHIVE_REDIS_URL`, `CODEHIVE_ANTHROPIC_API_KEY`, `CODEHIVE_ANTHROPIC_BASE_URL`
- [x] `.gitignore` still ignores `.env` (no regression)
- [x] No real secrets are committed anywhere in the repo
- [x] `uv run pytest backend/tests/test_config.py -v` passes with all existing tests plus new tests (8+ tests total)

## Test Scenarios

### Unit: Settings loads from .env file
- Create a temporary `.env` file with `CODEHIVE_HOST=10.0.0.1`, instantiate `Settings()` with that env_file, verify `settings.host == "10.0.0.1"`
- Create a temporary `.env` file with `CODEHIVE_ANTHROPIC_API_KEY=sk-test-123`, instantiate `Settings()`, verify the key is loaded
- Verify that when no `.env` file exists and no env var is set, `anthropic_api_key` defaults to empty string (or whatever the chosen default is)

### Unit: Env vars override .env file
- Create a `.env` file with `CODEHIVE_PORT=3000`, also set env var `CODEHIVE_PORT=4000` via monkeypatch, verify `settings.port == 4000`

### Unit: Anthropic fields exist and have correct defaults
- Instantiate `Settings()` without any Anthropic env vars, verify `anthropic_api_key` and `anthropic_base_url` have sensible default values
- Override via env var, verify they pick up the new value

### Validation: .env.example completeness
- Verify `.env.example` contains entries for all fields defined in `Settings` (can be a test or manual check)

## Out of Scope
- Secret rotation or expiry
- Encrypted storage or vault integration
- Per-project secrets
- Secrets masking in logs (separate issue)

## Log

### [SWE] 2026-03-15 12:00
- Added `env_file = ".env"` and `env_file_encoding = "utf-8"` to `Settings.model_config`
- Added `anthropic_api_key: str = ""` and `anthropic_base_url: str = ""` fields to `Settings`
- Updated `.env.example` to include all CODEHIVE_ prefixed variables with placeholder values and comments
- Verified `.gitignore` already correctly ignores `.env` -- no changes needed
- Files modified: `backend/codehive/config.py`, `.env.example`, `backend/tests/test_config.py`
- Tests added: 9 new tests (4 Anthropic field tests, 4 env file loading tests, 1 env.example completeness test)
- Build results: 19 config tests pass (10 existing + 9 new), 116 total tests pass, ruff clean
- Known limitations: none

### [QA] 2026-03-15 12:30
- Tests: 159 passed, 0 failed (19 config tests, 159 total)
- Ruff check: clean
- Ruff format: clean (34 files already formatted)
- Acceptance criteria:
  - Settings.model_config includes env_file pointing to .env: PASS
  - Settings has anthropic_api_key and anthropic_base_url fields with defaults: PASS
  - Instantiating Settings() with a .env file picks up values: PASS
  - Environment variables override .env file values: PASS
  - .env.example contains every variable with placeholder values and comments: PASS
  - .env.example includes all required CODEHIVE_ variables: PASS
  - .gitignore still ignores .env: PASS
  - No real secrets committed in repo: PASS
  - pytest passes with 8+ config tests (19 total config tests, 9 new): PASS
- VERDICT: PASS

### [PM] 2026-03-15 13:00
- Reviewed diff: 3 files changed (config.py +8/-1, .env.example +12/-5, test_config.py +86)
- Results verified: real data present -- 19 config tests pass, 159 total, ruff clean
- Acceptance criteria: all 9 met
  1. model_config has env_file=".env" and env_file_encoding="utf-8": MET
  2. anthropic_api_key and anthropic_base_url fields with "" defaults: MET
  3. .env file loading verified via TestEnvFileLoading (tmp_path + _env_file): MET
  4. Env var override of .env tested in test_env_var_overrides_env_file: MET
  5. .env.example has all vars with placeholders and section comments: MET
  6. All 7 required CODEHIVE_ vars present, validated by test: MET
  7. .gitignore lines 39-41 still ignore .env: MET
  8. No real secrets in repo (grep confirmed): MET
  9. 19 config tests (10 existing + 9 new), well above 8+ threshold: MET
- Code quality: clean, minimal, follows existing patterns. No over-engineering.
- Tests are meaningful: cover defaults, overrides, env file loading, precedence, missing file fallback, and .env.example completeness.
- Follow-up issues created: none needed
- VERDICT: ACCEPT
