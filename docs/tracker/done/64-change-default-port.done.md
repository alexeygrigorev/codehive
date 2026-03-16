# 64: Change Default Port to 7433

## Description
Change the default API server port from 8000 to 7433. Update all references across the codebase -- source code, configuration, tests, documentation, and Docker files.

## Scope

### Source files (production code)
- `backend/codehive/config.py` -- change `port: int = 8000` to `port: int = 7433`
- `backend/codehive/cli.py` -- change `DEFAULT_BASE_URL` and help text from 8000 to 7433
- `backend/codehive/clients/telegram/bot.py` -- change default `base_url` parameter from 8000 to 7433
- `web/src/api/client.ts` -- change fallback base URL from `http://localhost:8000` to `http://localhost:7433`

### Configuration and infrastructure
- `.env.example` -- update `CODEHIVE_PORT=7433`
- `web/.env.example` -- update `VITE_API_BASE_URL=http://localhost:7433`
- `docker-compose.prod.yml` -- update port mapping and env default from 8000 to 7433
- `backend/Dockerfile` -- change `EXPOSE 8000` to `EXPOSE 7433` and update healthcheck URL
- `backend/docker-entrypoint.sh` -- change uvicorn `--port 8000` to `--port 7433`

### Documentation
- `README.md` -- update all port 8000 references to 7433

### Test files
- `backend/tests/test_config.py` -- update default port assertion
- `backend/tests/test_docker_prod.py` -- update EXPOSE and port assertions
- `backend/tests/test_tui.py` -- update all `http://localhost:8000` and `http://test:8000` references
- `backend/tests/test_tui_session.py` -- update all port 8000 references
- `backend/tests/test_rescue.py` -- update all port 8000 references
- `backend/tests/test_telegram.py` -- update all port 8000 references
- `web/src/test/*.test.ts` and `web/src/test/*.test.tsx` -- update all `http://localhost:8000` and `ws://localhost:8000` references

### Other tracker issues (docs only, do not block this issue)
- `docs/tracker/57b-nginx-frontend-deploy.todo.md` -- update reverse proxy port references
- Done files in `docs/tracker/done/` -- leave as-is (historical records)

## Out of scope
- `docs/concept-brainstorm.md` -- conceptual notes, not operational
- `docs/tracker/done/*.done.md` -- historical records, must not be modified

## Acceptance Criteria

- [ ] `grep -r "8000" backend/codehive/` returns zero matches (excluding `uv.lock`)
- [ ] `grep -r ":8000" web/src/api/` returns zero matches
- [ ] `backend/codehive/config.py` has `port: int = 7433`
- [ ] `backend/codehive/cli.py` has `DEFAULT_BASE_URL = "http://127.0.0.1:7433"` and updated help text
- [ ] `backend/codehive/clients/telegram/bot.py` default base_url is `http://127.0.0.1:7433`
- [ ] `web/src/api/client.ts` fallback URL is `http://localhost:7433`
- [ ] `.env.example` has `CODEHIVE_PORT=7433`
- [ ] `web/.env.example` has `VITE_API_BASE_URL=http://localhost:7433`
- [ ] `docker-compose.prod.yml` maps port 7433 and sets default env to 7433
- [ ] `backend/Dockerfile` has `EXPOSE 7433` and healthcheck uses port 7433
- [ ] `backend/docker-entrypoint.sh` runs uvicorn on port 7433
- [ ] `README.md` contains no references to port 8000
- [ ] `uv run pytest backend/tests/ -v` passes with all existing tests (updated for 7433)
- [ ] `cd web && npx vitest run` passes with all existing tests (updated for 7433)
- [ ] `docs/tracker/57b-nginx-frontend-deploy.todo.md` reverse proxy references updated to 7433

## Test Scenarios

### Unit: Config default port
- `Settings()` with no env vars returns `port == 7433`

### Unit: CLI default base URL
- `DEFAULT_BASE_URL` equals `http://127.0.0.1:7433`

### Unit: Docker files
- Dockerfile contains `EXPOSE 7433`
- docker-compose.prod.yml port mapping is `7433:7433`

### Integration: All existing tests pass
- All backend tests pass after port references are updated from 8000 to 7433
- All frontend tests pass after port references are updated from 8000 to 7433

### Verification: No stale references
- `grep -rn "8000"` across `backend/codehive/`, `web/src/`, `.env.example`, `README.md`, `docker-compose.prod.yml`, `backend/Dockerfile`, `backend/docker-entrypoint.sh` returns zero matches (excluding uv.lock and done tracker files)

## Dependencies
- None

## Log

### [SWE] 2026-03-16 09:07
- Changed default port from 8000 to 7433 across entire codebase
- Source files modified:
  - `backend/codehive/config.py` -- port default 8000 -> 7433
  - `backend/codehive/cli.py` -- DEFAULT_BASE_URL and help text
  - `backend/codehive/clients/telegram/bot.py` -- default base_url parameter
  - `web/src/api/client.ts` -- fallback base URL
- Configuration/infrastructure files modified:
  - `.env.example` -- CODEHIVE_PORT
  - `web/.env.example` -- VITE_API_BASE_URL
  - `docker-compose.prod.yml` -- port mapping and env default
  - `backend/Dockerfile` -- EXPOSE and healthcheck URL
  - `backend/docker-entrypoint.sh` -- uvicorn --port
- Documentation modified:
  - `README.md` -- all port references
  - `docs/tracker/57b-nginx-frontend-deploy.todo.md` -- reverse proxy references
- Test files updated (all 8000 -> 7433):
  - `backend/tests/test_config.py`
  - `backend/tests/test_docker_prod.py`
  - `backend/tests/test_tui.py`
  - `backend/tests/test_tui_session.py`
  - `backend/tests/test_rescue.py`
  - `backend/tests/test_telegram.py`
  - 18 web test files in `web/src/test/`
- Build results: 1123 backend tests pass, 341 frontend tests pass, ruff clean
- No new tests added (existing tests updated to reflect new port)
- Known limitations: none

### [QA] 2026-03-16 09:12
- Backend tests: 1123 passed, 0 failed (72.9s)
- Frontend tests: 341 passed, 0 failed (10.7s)
- Ruff check: clean (all checks passed)
- Ruff format: clean (176 files already formatted)
- Acceptance criteria:
  - `grep -r "8000" backend/codehive/` returns zero matches: PASS
  - `grep -r ":8000" web/src/api/` returns zero matches: PASS
  - `backend/codehive/config.py` has `port: int = 7433`: PASS
  - `backend/codehive/cli.py` has `DEFAULT_BASE_URL = "http://127.0.0.1:7433"` and updated help text: PASS
  - `backend/codehive/clients/telegram/bot.py` default base_url is `http://127.0.0.1:7433`: PASS
  - `web/src/api/client.ts` fallback URL is `http://localhost:7433`: PASS
  - `.env.example` has `CODEHIVE_PORT=7433`: PASS
  - `web/.env.example` has `VITE_API_BASE_URL=http://localhost:7433`: PASS
  - `docker-compose.prod.yml` maps port 7433 and sets default env to 7433: PASS
  - `backend/Dockerfile` has `EXPOSE 7433` and healthcheck uses port 7433: PASS
  - `backend/docker-entrypoint.sh` runs uvicorn on port 7433: PASS
  - `README.md` contains no references to port 8000: PASS
  - `uv run pytest backend/tests/ -v` passes: PASS (1123 tests)
  - `cd web && npx vitest run` passes: PASS (341 tests)
  - `docs/tracker/57b-nginx-frontend-deploy.todo.md` updated to 7433: PASS
- No stale 8000 references found in backend/codehive/, backend/tests/, web/src/, docker-compose.prod.yml, Dockerfile, docker-entrypoint.sh
- Note: working tree contains unrelated uncommitted changes (knowledge.py endpoint from issue 56, deleted 56-knowledge-auto-populate.groomed.md) -- not part of this issue, does not affect verdict
- VERDICT: PASS

### [PM] 2026-03-16 09:20
- Reviewed diff: 34 files changed, 129 insertions, 129 deletions (perfectly symmetric replacement)
- Results verified: real data present -- 1123 backend tests, 341 frontend tests, grep confirms zero stale 8000 references
- Spot-checked key files: config.py, cli.py, bot.py, client.ts, Dockerfile, docker-compose.prod.yml, docker-entrypoint.sh, .env.example, web/.env.example, README.md, 57b tracker issue
- Acceptance criteria: all 15 met
  1. No 8000 in backend/codehive/: PASS
  2. No :8000 in web/src/api/: PASS
  3. config.py port default 7433: PASS
  4. cli.py DEFAULT_BASE_URL 7433 + help text: PASS
  5. telegram bot.py default base_url 7433: PASS
  6. web client.ts fallback 7433: PASS
  7. .env.example CODEHIVE_PORT=7433: PASS
  8. web/.env.example VITE_API_BASE_URL localhost:7433: PASS
  9. docker-compose.prod.yml 7433:7433 mapping + env default: PASS
  10. Dockerfile EXPOSE 7433 + healthcheck 7433: PASS
  11. docker-entrypoint.sh uvicorn --port 7433: PASS
  12. README.md zero 8000 references: PASS
  13. Backend tests pass (1123): PASS
  14. Frontend tests pass (341): PASS
  15. 57b tracker updated to 7433: PASS
- Follow-up issues created: none needed
- VERDICT: ACCEPT
