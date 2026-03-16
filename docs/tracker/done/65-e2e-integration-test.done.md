# 65: End-to-End Integration Test

## Description

Wire everything together in a single test module that exercises the full user flow against the real FastAPI app backed by an in-memory SQLite database: register a user, log in, create a workspace, create a project, start a session, send a message, and verify the response. The engine (LLM call) must be mocked so tests run without an API key, but every other layer -- routing, auth, permissions, DB models, core logic -- must be exercised for real.

This is the "vertical slice" smoke test that catches integration breakage between layers.

## Dependencies

- Depends on: #01 (FastAPI setup), #03 (DB models), #04 (project CRUD), #05 (session CRUD), #09 (engine adapter), #59a (auth/JWT)
- All dependencies are `.done.md`.

## Scope

- One new test file: `backend/tests/test_e2e.py`
- Uses `httpx.AsyncClient` with the real FastAPI app (via `ASGITransport`)
- Uses an in-memory SQLite database (`sqlite+aiosqlite://`) with tables created via `Base.metadata.create_all`
- Overrides `get_db` and `_SessionFactory` to point at the test database
- Mocks only the engine layer (`_build_engine` in sessions route) to return deterministic events without calling Anthropic
- No Docker, no Redis, no external services required

## Acceptance Criteria

- [ ] `uv run pytest backend/tests/test_e2e.py -v` passes with 6+ tests
- [ ] Test file exists at `backend/tests/test_e2e.py`
- [ ] Tests use `pytest` + `pytest-asyncio` with `httpx.AsyncClient` (not `TestClient`)
- [ ] A shared async fixture sets up: in-memory SQLite engine, creates all tables, overrides FastAPI `get_db` dependency
- [ ] The full flow is tested end-to-end in sequence: register -> login -> create workspace -> create project -> create session -> send message
- [ ] The engine/LLM layer is mocked (no real Anthropic API calls) but returns realistic event structures
- [ ] Auth is tested for real: register returns tokens, login returns tokens, protected endpoints reject requests without a valid Bearer token
- [ ] Workspace creation returns 201 and the creator is auto-assigned as owner
- [ ] Project creation under the workspace returns 201
- [ ] Session creation under the project returns 201 with status `idle`
- [ ] Sending a message to the session returns engine events (from the mock)
- [ ] At least one negative test: accessing a protected endpoint without auth returns 401
- [ ] All tests are independent of external services (no Postgres, no Redis, no Anthropic key)

## Test Scenarios

### Fixture: async app with SQLite

- Create an async SQLAlchemy engine pointing at `sqlite+aiosqlite://`
- Run `Base.metadata.create_all` to create all tables
- Override `codehive.api.deps.get_db` to yield sessions from the test engine
- Build `httpx.AsyncClient` with `ASGITransport(app=create_app())`

### E2E: Full user journey (happy path)

1. **Register** -- POST `/api/auth/register` with email, username, password. Verify 201, response contains `access_token` and `refresh_token`.
2. **Login** -- POST `/api/auth/login` with the same credentials. Verify 200, response contains tokens.
3. **Get current user** -- GET `/api/auth/me` with Bearer token. Verify 200, response contains the registered email and username.
4. **Create workspace** -- POST `/api/workspaces` with name and root_path. Verify 201, response contains workspace `id`.
5. **Create project** -- POST `/api/projects` with `workspace_id`, name. Verify 201, response contains project `id` and correct `workspace_id`.
6. **Create session** -- POST `/api/projects/{project_id}/sessions` with name, engine=`native`, mode=`execution`. Verify 201, response contains session `id`, status is `idle`.
7. **Send message** -- POST `/api/sessions/{session_id}/messages` with content. Mock `_build_engine` to return a fake engine yielding `[{"type": "message.created", "data": {"content": "Hello from mock"}}]`. Verify 200, response is a list of event dicts.

### E2E: Auth rejection

- GET `/api/workspaces` without Authorization header. Verify 401.
- GET `/api/workspaces` with an invalid/expired token. Verify 401.

### E2E: Entity relationships

- After creating workspace + project + session, GET `/api/workspaces/{id}/projects` returns the project.
- GET `/api/projects/{project_id}/sessions` returns the session.

## Implementation Notes

- The `send_message_endpoint` calls `_build_engine` which constructs a real engine. Tests must patch `codehive.api.routes.sessions._build_engine` to return an async mock engine whose `send_message` is an async generator yielding test events.
- SQLite does not support all PostgreSQL features. If any model uses PostgreSQL-specific types (e.g., `JSONB`), the test setup may need `JSON` fallback. Check existing test patterns in the codebase.
- The lifespan handler in `create_app` calls `seed_first_run`. The test must either let this run against the test DB or override the lifespan to be a no-op. Either approach is acceptable as long as it does not mask real bugs.

## Log

### [SWE] 2026-03-16 12:00
- Implemented E2E integration test covering the full user journey
- Created `backend/tests/test_e2e.py` with 7 tests across 3 test classes:
  - TestE2EHappyPath (4 tests): register, login, get current user, full journey (register -> login -> workspace -> project -> session -> send message)
  - TestE2EAuthRejection (2 tests): no auth returns 401, invalid token returns 401
  - TestE2EEntityRelationships (1 test): workspace/projects and project/sessions listing
- Used same SQLite-compatible metadata pattern as test_auth.py (JSONB->JSON, server_default fixups)
- Mocked only `_build_engine` via `unittest.mock.patch` -- all other layers (routing, auth, permissions, DB) are real
- The lifespan `seed_first_run` runs against the test DB; tests register separate users to avoid conflicts with seeded admin
- Files created: `backend/tests/test_e2e.py`
- Tests added: 7 tests covering all acceptance criteria
- Build results: 7 tests pass, 0 fail, ruff clean

### [QA] 2026-03-16 12:30
- Tests: 7 passed, 0 failed (test_e2e.py); full suite 1384 passed, 3 skipped
- Ruff: clean (check and format)
- Acceptance criteria:
  1. 6+ tests pass: PASS (7 tests)
  2. Test file exists at backend/tests/test_e2e.py: PASS
  3. Uses pytest + pytest-asyncio + httpx.AsyncClient: PASS
  4. Shared async fixture with SQLite + table creation + get_db override: PASS
  5. Full flow tested (register -> login -> workspace -> project -> session -> message): PASS
  6. Engine/LLM mocked with realistic events: PASS
  7. Auth tested for real (tokens returned, rejection without token): PASS
  8. Workspace creation returns 201: PASS
  9. Project creation returns 201: PASS
  10. Session creation returns 201 with status idle: PASS
  11. Sending message returns mock engine events: PASS
  12. Negative test (401 without auth): PASS (two negative tests)
  13. Independent of external services: PASS
- VERDICT: PASS

### [PM] 2026-03-16 13:00
- Reviewed diff: 1 file changed (backend/tests/test_e2e.py, 326 lines)
- Results verified: real data present -- 7 tests pass in 3.15s, full vertical slice exercised
- Acceptance criteria: all 13 met
  1. 7 tests pass (>=6 required)
  2. Test file exists at backend/tests/test_e2e.py
  3. Uses pytest + pytest-asyncio + httpx.AsyncClient with ASGITransport
  4. Shared async fixture: in-memory SQLite engine, create_all, get_db override
  5. Full flow: register -> login -> workspace -> project -> session -> message
  6. Engine mocked with realistic event structure (message.created)
  7. Auth tested for real: tokens returned on register/login, 401 on rejection
  8. Workspace creation returns 201
  9. Project creation returns 201
  10. Session creation returns 201, status idle
  11. Message returns mock engine events, verified type and content
  12. Two negative tests: no auth header (401), invalid token (401)
  13. No external services: in-memory SQLite, mocked engine
- Code quality: clean, well-structured, follows existing test_auth.py patterns for SQLite compat
- Follow-up issues created: none
- VERDICT: ACCEPT
