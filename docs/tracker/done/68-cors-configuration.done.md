# 68: CORS Configuration

## Description

Add CORS middleware to the FastAPI application so the web frontend (and other allowed origins) can make cross-origin requests to the backend API. Origins are configurable via the `CODEHIVE_CORS_ORIGINS` environment variable, defaulting to `http://localhost:5173` (Vite dev server).

## Dependencies

- Depends on: #01 (FastAPI app) -- done

## Scope

1. Add a `cors_origins` setting to `Settings` in `backend/codehive/config.py`, parsed from the `CODEHIVE_CORS_ORIGINS` env var as a comma-separated list of origins. Default: `["http://localhost:5173"]`.
2. In `create_app()` (`backend/codehive/api/app.py`), add `CORSMiddleware` from `starlette.middleware.cors` (or `fastapi.middleware.cors`) using the configured origins. Allow credentials, all methods, and all headers.
3. Add tests that verify CORS behavior.

## Acceptance Criteria

- [ ] `backend/codehive/config.py` has a `cors_origins: list[str]` field defaulting to `["http://localhost:5173"]`
- [ ] Setting `CODEHIVE_CORS_ORIGINS=http://example.com,http://other.com` correctly populates `cors_origins` with two entries
- [ ] `CORSMiddleware` is added to the FastAPI app in `create_app()`
- [ ] A preflight `OPTIONS` request to any API endpoint with `Origin: http://localhost:5173` returns `Access-Control-Allow-Origin: http://localhost:5173`
- [ ] A request with an origin NOT in the allowed list does NOT receive `Access-Control-Allow-Origin` in the response
- [ ] `Access-Control-Allow-Credentials` is `true` in CORS responses
- [ ] `Access-Control-Allow-Methods` includes GET, POST, PUT, DELETE, PATCH, OPTIONS
- [ ] `uv run pytest tests/test_cors.py -v` passes with 4+ tests

## Test Scenarios

### Unit: Settings parsing
- Default `cors_origins` equals `["http://localhost:5173"]` when env var is unset
- Setting `CODEHIVE_CORS_ORIGINS` to a comma-separated string produces the correct list

### Integration: CORS middleware behavior
- `OPTIONS /api/health` with `Origin: http://localhost:5173` and `Access-Control-Request-Method: GET` returns 200 with correct CORS headers (`Access-Control-Allow-Origin`, `Access-Control-Allow-Credentials`, `Access-Control-Allow-Methods`)
- `GET /api/health` with `Origin: http://localhost:5173` returns the `Access-Control-Allow-Origin` header in the response
- `GET /api/health` with `Origin: http://evil.com` (not in allowed list) does NOT return `Access-Control-Allow-Origin`
- Custom origins via env var are respected: setting origins to `http://custom.dev` and sending a request with that origin returns correct CORS headers

## Implementation Notes

- `CORSMiddleware` is built into Starlette/FastAPI, no extra dependency needed.
- The middleware must be added before routes are included (or after -- order does not matter for middleware in FastAPI since `add_middleware` prepends).
- For the comma-separated env var parsing, consider a custom validator on the `cors_origins` field or use pydantic's built-in list parsing with a separator.

## Log

### [SWE] 2026-03-16 12:00
- Added `cors_origins: list[str]` field to Settings with default `["http://localhost:5173"]`
- Created custom `_CorsEnvSource(EnvSettingsSource)` to parse comma-separated strings for cors_origins (pydantic-settings v2 JSON-decodes complex env vars by default, so a custom source is needed to support comma-separated input)
- Added `settings_customise_sources` classmethod to Settings to wire in the custom env source
- Added CORSMiddleware to `create_app()` using `settings.cors_origins` with `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`
- Files modified: `backend/codehive/config.py`, `backend/codehive/api/app.py`
- Files created: `backend/tests/test_cors.py`
- Tests added: 8 tests (4 unit for config parsing, 4 integration for CORS middleware behavior)
- Build results: 8 tests pass in test_cors.py, 25 pass in test_config.py + test_api.py, 0 fail, ruff clean
- No new dependencies added (CORSMiddleware is built into FastAPI/Starlette)

### [QA] 2026-03-16 12:30
- Tests: 8 passed, 0 failed (test_cors.py); 25 passed in test_config.py + test_api.py
- Ruff: clean (check and format both pass)
- Acceptance criteria:
  - `cors_origins: list[str]` field with default `["http://localhost:5173"]`: PASS
  - Comma-separated env var parsing produces correct list: PASS
  - `CORSMiddleware` added in `create_app()`: PASS
  - Preflight OPTIONS with allowed origin returns correct header: PASS
  - Disallowed origin does NOT receive `Access-Control-Allow-Origin`: PASS
  - `Access-Control-Allow-Credentials` is `true`: PASS
  - `Access-Control-Allow-Methods` includes GET, POST, PUT, DELETE, PATCH, OPTIONS: PASS
  - `uv run pytest tests/test_cors.py -v` passes with 4+ tests (8 tests): PASS
- VERDICT: PASS

### [PM] 2026-03-16 13:00
- Reviewed diff: 2 files changed (config.py, app.py), 1 test file created (test_cors.py)
- Results verified: real data present -- 8 tests pass, all CORS headers confirmed in test output
- Acceptance criteria: all 8 met
  - cors_origins field with correct default: MET
  - Comma-separated env var parsing: MET
  - CORSMiddleware added in create_app(): MET
  - Preflight OPTIONS returns correct headers: MET
  - Disallowed origin blocked: MET
  - Allow-Credentials true: MET
  - Allow-Methods includes all required methods: MET
  - 4+ tests (8 tests pass): MET
- Code quality: clean, idiomatic. Custom EnvSettingsSource for comma parsing is the right approach for pydantic-settings v2.
- Follow-up issues created: none needed
- VERDICT: ACCEPT
