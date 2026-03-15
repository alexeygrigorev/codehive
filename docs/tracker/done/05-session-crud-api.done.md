# 05: Session CRUD API

## Description
REST API endpoints for creating, listing, reading, updating, and managing sessions within a project. Includes Pydantic request/response schemas, a business logic layer with session state machine validation, and comprehensive tests using an in-memory SQLite database (no Docker required for tests). Follows the same patterns established in issue #04 (Project CRUD API).

## Scope
- `backend/codehive/api/routes/sessions.py` — CRUD + status transition endpoints
- `backend/codehive/api/schemas/session.py` — Pydantic models for request/response
- `backend/codehive/core/session.py` — Session business logic (DB queries, state machine)
- `backend/codehive/api/app.py` — updated to register the sessions router
- `backend/tests/test_sessions.py` — API tests (CRUD happy path + error cases + state transitions)

## Endpoints

Sessions use two URL prefixes: project-scoped for creation/listing, and flat for operations on existing sessions.

| Method | Path | Description | Status Code |
|--------|------|-------------|-------------|
| POST | `/api/projects/{project_id}/sessions` | Create a session | 201 (404 if project not found) |
| GET | `/api/projects/{project_id}/sessions` | List sessions for a project | 200 (404 if project not found) |
| GET | `/api/sessions/{id}` | Get a single session | 200 (404 if not found) |
| PATCH | `/api/sessions/{id}` | Update session (mode, config, name) | 200 (404 if not found) |
| DELETE | `/api/sessions/{id}` | Delete a session | 204 (404 if not found, 409 if has children) |
| POST | `/api/sessions/{id}/pause` | Pause a session | 200 (404 if not found, 409 if invalid transition) |
| POST | `/api/sessions/{id}/resume` | Resume a session | 200 (404 if not found, 409 if invalid transition) |

### Request/Response Schemas

**SessionCreate** (POST body):
- `name`: str (required, max 255 chars)
- `engine`: str (required, max 50 chars) -- e.g. "native", "claude_code"
- `mode`: str (required, max 50 chars) -- e.g. "execution", "brainstorm", "interview", "planning", "review"
- `issue_id`: UUID | null (optional) -- FK to an existing issue
- `parent_session_id`: UUID | null (optional) -- FK to a parent session (sub-agent)
- `config`: dict (optional, default `{}`)

Note: `project_id` comes from the URL path, not the request body.

**SessionUpdate** (PATCH body -- all fields optional):
- `name`: str | null
- `mode`: str | null
- `config`: dict | null

Note: `status`, `engine`, `project_id`, `issue_id`, and `parent_session_id` are NOT updatable via PATCH. Status changes happen only through dedicated action endpoints (pause/resume) or internal state machine transitions.

**SessionRead** (response):
- `id`: UUID
- `project_id`: UUID
- `issue_id`: UUID | null
- `parent_session_id`: UUID | null
- `name`: str
- `engine`: str
- `mode`: str
- `status`: str
- `config`: dict
- `created_at`: datetime

## Session Statuses and State Machine

Valid statuses: `idle`, `planning`, `executing`, `waiting_input`, `waiting_approval`, `blocked`, `completed`, `failed`

New sessions are created with status `idle`.

### Pause/Resume Rules

**Pause** (`POST /api/sessions/{id}/pause`):
- Allowed from: `idle`, `planning`, `executing`
- NOT allowed from: `waiting_input`, `waiting_approval`, `blocked`, `completed`, `failed`
- Sets status to `blocked`
- Returns 409 Conflict with descriptive message if transition is not allowed

**Resume** (`POST /api/sessions/{id}/resume`):
- Allowed from: `blocked`
- NOT allowed from any other status
- Sets status to `idle`
- Returns 409 Conflict with descriptive message if transition is not allowed

## Design Decisions

- **Project must exist.** POST `/api/projects/{project_id}/sessions` requires a valid project_id. Return 404 if the project does not exist.
- **issue_id and parent_session_id are validated** if provided. Return 404 with descriptive message if they reference non-existent records.
- **No cascading deletes.** DELETE `/api/sessions/{id}` should fail with 409 Conflict if the session has child sessions (sub-agents). Clean deletion only.
- **Async SQLAlchemy** throughout. Same dependency injection pattern as projects.
- **Tests use SQLite in-memory** via `aiosqlite` -- no Docker needed. Reuse the same fixture pattern from `test_projects.py` (db_session, workspace, client).
- **Business logic in core layer.** Routes are thin HTTP translators; all DB queries and validation logic live in `core/session.py`.
- **State machine is simple.** Only pause/resume are exposed as API actions for now. Other status transitions (idle -> planning -> executing, etc.) will be driven by the engine in later issues.

## Dependencies
- Depends on: #04 (Project CRUD API -- DONE) -- needs project endpoints and patterns to follow
- Depends on: #03 (Database models -- DONE) -- Session model already exists with all required columns

## Acceptance Criteria

- [ ] `uv run pytest backend/tests/test_sessions.py -v` passes with 15+ tests
- [ ] POST `/api/projects/{project_id}/sessions` with valid payload returns 201 and the created session with `id`, `status` = "idle", and `created_at`
- [ ] POST `/api/projects/{project_id}/sessions` with non-existent `project_id` returns 404
- [ ] POST `/api/projects/{project_id}/sessions` with missing required fields returns 422
- [ ] POST `/api/projects/{project_id}/sessions` with non-existent `issue_id` returns 404
- [ ] POST `/api/projects/{project_id}/sessions` with non-existent `parent_session_id` returns 404
- [ ] GET `/api/projects/{project_id}/sessions` returns 200 with a JSON list of sessions for that project (empty list when none exist)
- [ ] GET `/api/projects/{project_id}/sessions` with non-existent project returns 404
- [ ] GET `/api/sessions/{id}` with valid ID returns 200 with full session data
- [ ] GET `/api/sessions/{id}` with non-existent ID returns 404
- [ ] PATCH `/api/sessions/{id}` with partial payload updates only the provided fields and returns 200
- [ ] PATCH `/api/sessions/{id}` with non-existent ID returns 404
- [ ] DELETE `/api/sessions/{id}` with valid ID returns 204 and the session is no longer retrievable
- [ ] DELETE `/api/sessions/{id}` with non-existent ID returns 404
- [ ] DELETE `/api/sessions/{id}` with child sessions returns 409 Conflict
- [ ] POST `/api/sessions/{id}/pause` from `idle` status returns 200 with status changed to `blocked`
- [ ] POST `/api/sessions/{id}/pause` from `completed` status returns 409 Conflict
- [ ] POST `/api/sessions/{id}/resume` from `blocked` status returns 200 with status changed to `idle`
- [ ] POST `/api/sessions/{id}/resume` from `idle` status returns 409 Conflict
- [ ] The sessions router is registered in `create_app()` so the server includes these routes
- [ ] Business logic lives in `backend/codehive/core/session.py`, not directly in route handlers
- [ ] All responses use Pydantic `response_model` for serialization

## Test Scenarios

### Unit: Core session operations (test with async SQLite)
- `create_session` persists a session with status "idle" and returns it with generated `id` and `created_at`
- `create_session` with non-existent project_id raises ProjectNotFoundError
- `create_session` with non-existent issue_id raises IssueNotFoundError
- `create_session` with non-existent parent_session_id raises SessionNotFoundError
- `list_sessions` for a project returns only that project's sessions (not sessions from other projects)
- `list_sessions` for empty project returns empty list
- `get_session` with valid ID returns the session
- `get_session` with non-existent ID returns None
- `update_session` modifies only specified fields (e.g. mode), leaves others unchanged
- `update_session` with non-existent ID raises SessionNotFoundError
- `delete_session` removes the session from the database
- `delete_session` with non-existent ID raises SessionNotFoundError
- `delete_session` with child sessions raises SessionHasDependentsError
- `pause_session` from "idle" sets status to "blocked"
- `pause_session` from "completed" raises InvalidStatusTransitionError
- `resume_session` from "blocked" sets status to "idle"
- `resume_session` from "idle" raises InvalidStatusTransitionError

### Integration: API endpoints (via FastAPI TestClient)
- POST /api/projects/{project_id}/sessions with valid body -> 201, response matches SessionRead schema, status is "idle"
- POST /api/projects/{project_id}/sessions missing required fields -> 422 validation error
- POST /api/projects/{bad-uuid}/sessions -> 404
- POST /api/projects/{project_id}/sessions with bad issue_id -> 404
- POST /api/projects/{project_id}/sessions with bad parent_session_id -> 404
- GET /api/projects/{project_id}/sessions -> 200, returns list (test with 0 and 2+ sessions)
- GET /api/projects/{bad-uuid}/sessions -> 404
- GET /api/sessions/{id} -> 200 with correct data
- GET /api/sessions/{unknown-uuid} -> 404
- PATCH /api/sessions/{id} with `{"mode": "review"}` -> 200, only mode changed
- PATCH /api/sessions/{unknown-uuid} -> 404
- DELETE /api/sessions/{id} -> 204, subsequent GET -> 404
- DELETE /api/sessions/{unknown-uuid} -> 404
- DELETE /api/sessions/{id} with child sessions -> 409
- POST /api/sessions/{id}/pause from idle -> 200, status is "blocked"
- POST /api/sessions/{id}/pause from completed -> 409
- POST /api/sessions/{id}/resume from blocked -> 200, status is "idle"
- POST /api/sessions/{id}/resume from idle -> 409

## Log

### [SWE] 2026-03-15 10:00
- Implemented Session CRUD API following exact same patterns as Project CRUD (issue #04)
- Created Pydantic schemas (SessionCreate, SessionUpdate, SessionRead) in schemas/session.py
- Created business logic layer in core/session.py with all CRUD operations plus pause/resume state machine
- Created routes in api/routes/sessions.py with two routers: project-scoped (create/list) and flat (get/update/delete/pause/resume)
- Registered both routers in create_app()
- Custom exceptions: ProjectNotFoundError, IssueNotFoundError, SessionNotFoundError, SessionHasDependentsError, InvalidStatusTransitionError
- Pause allowed from: idle, planning, executing -> blocked; Resume allowed from: blocked -> idle
- FK validation for issue_id and parent_session_id on create
- Delete blocked with 409 if session has child sessions
- Files created: backend/codehive/api/schemas/session.py, backend/codehive/core/session.py, backend/codehive/api/routes/sessions.py
- Files modified: backend/codehive/api/app.py
- Tests added: 43 tests (22 unit core + 21 integration API) in backend/tests/test_sessions.py
- Build results: 159 tests pass (all), 0 fail, ruff clean, format clean

### [QA] 2026-03-15 11:00
- Tests: 159 passed (43 session-specific), 0 failed
- Ruff: clean (check + format)
- Acceptance criteria:
  - [x] 15+ tests in test_sessions.py: PASS (43 tests)
  - [x] POST create 201 with id/status/created_at: PASS
  - [x] POST create non-existent project 404: PASS
  - [x] POST create missing fields 422: PASS
  - [x] POST create non-existent issue_id 404: PASS
  - [x] POST create non-existent parent_session_id 404: PASS
  - [x] GET list 200 with JSON list: PASS
  - [x] GET list non-existent project 404: PASS
  - [x] GET session 200 with full data: PASS
  - [x] GET session non-existent 404: PASS
  - [x] PATCH partial update 200: PASS
  - [x] PATCH non-existent 404: PASS
  - [x] DELETE 204 and session gone: PASS
  - [x] DELETE non-existent 404: PASS
  - [x] DELETE with children 409: PASS
  - [x] POST pause from idle 200 -> blocked: PASS
  - [x] POST pause from completed 409: PASS
  - [x] POST resume from blocked 200 -> idle: PASS
  - [x] POST resume from idle 409: PASS
  - [x] Sessions router registered in create_app(): PASS
  - [x] Business logic in core/session.py: PASS
  - [x] All responses use Pydantic response_model: PASS
- VERDICT: PASS

### [PM] 2026-03-15 12:15
- Reviewed diff: 4 new files (schemas/session.py, core/session.py, routes/sessions.py, tests/test_sessions.py) + 1 modified (api/app.py)
- Results verified: real data present -- 43/43 session tests pass, 159/159 full suite passes, all 7 endpoints functional
- Acceptance criteria: all 22 met
  - [x] 43 tests (requirement: 15+)
  - [x] POST create 201 with id, status=idle, created_at
  - [x] POST non-existent project 404
  - [x] POST missing fields 422
  - [x] POST non-existent issue_id 404
  - [x] POST non-existent parent_session_id 404
  - [x] GET list 200 with JSON list (empty and populated)
  - [x] GET list non-existent project 404
  - [x] GET session 200 with full data
  - [x] GET session non-existent 404
  - [x] PATCH partial update 200 (only specified fields changed)
  - [x] PATCH non-existent 404
  - [x] DELETE 204 and session gone (verified with subsequent GET 404)
  - [x] DELETE non-existent 404
  - [x] DELETE with children 409 Conflict
  - [x] Pause from idle -> blocked 200
  - [x] Pause from completed -> 409 Conflict
  - [x] Resume from blocked -> idle 200
  - [x] Resume from idle -> 409 Conflict
  - [x] Sessions router registered in create_app()
  - [x] Business logic in core/session.py, routes are thin HTTP translators
  - [x] All responses use Pydantic response_model
- Code quality: clean separation of concerns, proper FK validation, state machine correctly constrained, follows project CRUD patterns from issue #04
- Follow-up issues created: none needed
- VERDICT: ACCEPT
