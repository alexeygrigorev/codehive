# 04: Project CRUD API

## Description
REST API endpoints for creating, listing, reading, updating, and deleting projects. Includes Pydantic request/response schemas, a business logic layer, and comprehensive tests using an in-memory SQLite database (no Docker required for tests).

## Scope
- `backend/codehive/api/routes/__init__.py` — package init
- `backend/codehive/api/routes/projects.py` — CRUD endpoints
- `backend/codehive/api/schemas/` — Pydantic models for request/response
- `backend/codehive/core/__init__.py` — package init
- `backend/codehive/core/project.py` — Project business logic (DB queries)
- `backend/codehive/api/deps.py` — FastAPI dependency for async DB session
- `backend/codehive/api/app.py` — updated to register the projects router
- `backend/tests/test_projects.py` — API tests (CRUD happy path + error cases)

## Endpoints

All endpoints are mounted under `/api/projects`.

| Method | Path | Description | Status Code |
|--------|------|-------------|-------------|
| POST | `/api/projects` | Create a project | 201 |
| GET | `/api/projects` | List all projects | 200 |
| GET | `/api/projects/{id}` | Get a single project | 200 (404 if not found) |
| PATCH | `/api/projects/{id}` | Partial update of a project | 200 (404 if not found) |
| DELETE | `/api/projects/{id}` | Delete a project | 204 (404 if not found) |

### Request/Response Schemas

**ProjectCreate** (POST body):
- `workspace_id`: UUID (required) -- FK to an existing workspace
- `name`: str (required, max 255 chars)
- `path`: str | null (optional)
- `description`: str | null (optional)
- `archetype`: str | null (optional)

**ProjectUpdate** (PATCH body -- all fields optional):
- `name`: str | null
- `path`: str | null
- `description`: str | null
- `archetype`: str | null

**ProjectRead** (response):
- `id`: UUID
- `workspace_id`: UUID
- `name`: str
- `path`: str | null
- `description`: str | null
- `archetype`: str | null
- `knowledge`: dict
- `created_at`: datetime

**ProjectList** (GET /api/projects response):
- List of ProjectRead objects

## Design Decisions

- **Workspace must exist.** POST /api/projects requires a valid `workspace_id`. Return 404 if the workspace does not exist.
- **No cascading deletes yet.** DELETE /api/projects/{id} should fail with 409 Conflict if the project has associated sessions or issues. Clean deletion only.
- **knowledge field is read-only** in CRUD -- it is not settable via POST or PATCH (managed by a separate knowledge-base endpoint in issue #48).
- **Async SQLAlchemy** throughout. The DB session dependency uses the async session factory from `db/session.py`.
- **Tests use SQLite in-memory** via `aiosqlite` -- no Docker needed. The test fixture creates tables from `Base.metadata`, provides an `AsyncSession`, and overrides the FastAPI DB dependency.

## Dependencies
- Depends on: #03 (database models -- DONE)
- No dependency on Docker running (tests use SQLite)

## Acceptance Criteria

- [ ] `uv run pytest backend/tests/test_projects.py -v` passes with 8+ tests
- [ ] POST `/api/projects` with valid payload returns 201 and the created project with `id` and `created_at`
- [ ] POST `/api/projects` with non-existent `workspace_id` returns 404
- [ ] POST `/api/projects` with missing required field `name` returns 422
- [ ] GET `/api/projects` returns 200 with a JSON list of projects (empty list when none exist)
- [ ] GET `/api/projects/{id}` with valid ID returns 200 with full project data
- [ ] GET `/api/projects/{id}` with non-existent ID returns 404
- [ ] PATCH `/api/projects/{id}` with partial payload updates only the provided fields and returns 200
- [ ] PATCH `/api/projects/{id}` with non-existent ID returns 404
- [ ] DELETE `/api/projects/{id}` with valid ID returns 204 and the project is no longer retrievable
- [ ] DELETE `/api/projects/{id}` with non-existent ID returns 404
- [ ] The projects router is registered in `create_app()` so the server includes these routes
- [ ] Business logic lives in `backend/codehive/core/project.py`, not directly in route handlers
- [ ] All responses use Pydantic `response_model` for serialization

## Test Scenarios

### Unit: Core project operations (test with async SQLite)
- `create_project` persists a project and returns it with generated `id` and `created_at`
- `create_project` with non-existent workspace_id raises appropriate error
- `list_projects` returns all projects
- `get_project` with valid ID returns the project
- `get_project` with non-existent ID returns None or raises NotFound
- `update_project` modifies only specified fields, leaves others unchanged
- `delete_project` removes the project from the database

### Integration: API endpoints (via FastAPI TestClient)
- POST /api/projects with valid body -> 201, response matches ProjectRead schema
- POST /api/projects missing `name` -> 422 validation error
- POST /api/projects with bad workspace_id -> 404
- GET /api/projects -> 200, returns list (test with 0 and 2+ projects)
- GET /api/projects/{id} -> 200 with correct data
- GET /api/projects/{unknown-uuid} -> 404
- PATCH /api/projects/{id} with `{"description": "updated"}` -> 200, only description changed
- PATCH /api/projects/{unknown-uuid} -> 404
- DELETE /api/projects/{id} -> 204, subsequent GET -> 404
- DELETE /api/projects/{unknown-uuid} -> 404

## Log

### [SWE] 2026-03-14 12:00
- Implemented full Project CRUD API with 5 endpoints (POST, GET list, GET by id, PATCH, DELETE)
- Created Pydantic schemas (ProjectCreate, ProjectUpdate, ProjectRead) in api/schemas/project.py
- Created business logic layer in core/project.py with create/list/get/update/delete operations
- Created FastAPI dependency for DB session injection in api/deps.py
- Created route handlers in api/routes/projects.py with proper error handling (404, 409, 422)
- Registered projects router in create_app()
- Added aiosqlite dev dependency for SQLite-based async tests
- Built SQLite-compatible metadata helper to handle Postgres-specific JSONB types and server_defaults
- Files created:
  - backend/codehive/api/schemas/__init__.py
  - backend/codehive/api/schemas/project.py
  - backend/codehive/api/routes/__init__.py
  - backend/codehive/api/routes/projects.py
  - backend/codehive/api/deps.py
  - backend/codehive/core/__init__.py
  - backend/codehive/core/project.py
  - backend/tests/test_projects.py
- Files modified:
  - backend/codehive/api/app.py (added router registration)
  - backend/pyproject.toml (added aiosqlite dev dep)
- Tests added: 21 tests (10 unit core logic + 11 integration API endpoints)
- Build results: 107 tests pass (all), 0 fail, ruff clean on issue files
- Known limitations: Pre-existing ruff warning in codehive/execution/shell.py (unused import, not from this issue)

### [QA] 2026-03-14 12:30
- Tests: 107 passed, 0 failed (21 project tests: 10 unit + 11 integration)
- Ruff check: clean (all checks passed)
- Ruff format: clean (30 files already formatted)
- Acceptance criteria:
  - 8+ tests in test_projects.py: PASS (21 tests)
  - POST /api/projects 201 with id and created_at: PASS
  - POST /api/projects non-existent workspace_id 404: PASS
  - POST /api/projects missing name 422: PASS
  - GET /api/projects 200 with JSON list: PASS
  - GET /api/projects/{id} 200 with full data: PASS
  - GET /api/projects/{id} non-existent 404: PASS
  - PATCH /api/projects/{id} partial update 200: PASS
  - PATCH /api/projects/{id} non-existent 404: PASS
  - DELETE /api/projects/{id} 204 and not retrievable: PASS
  - DELETE /api/projects/{id} non-existent 404: PASS
  - Router registered in create_app(): PASS
  - Business logic in core/project.py: PASS
  - All responses use Pydantic response_model: PASS
- VERDICT: PASS

### [PM] 2026-03-14 13:00
- Reviewed diff: 10 files changed (8 new, 2 modified: app.py, pyproject.toml)
- Results verified: real test data present -- 21 tests (10 unit + 11 integration) all pass, 107 total suite passes
- Code quality:
  - Clean separation of concerns: schemas (api/schemas/project.py), business logic (core/project.py), routes (api/routes/projects.py), dependency injection (api/deps.py)
  - Routes are thin HTTP translators; all DB logic in core layer
  - Custom exceptions (WorkspaceNotFoundError, ProjectNotFoundError, ProjectHasDependentsError) with proper HTTP mapping
  - SQLite-compatible test fixture handles JSONB/server_default differences cleanly
  - All endpoints use response_model for Pydantic serialization
  - 409 Conflict handling for cascade protection implemented in delete
- Acceptance criteria: all 14/14 met
  1. 21 tests pass (8+ required): MET
  2. POST 201 with id and created_at: MET
  3. POST non-existent workspace 404: MET
  4. POST missing name 422: MET
  5. GET list 200 with JSON list: MET
  6. GET by id 200: MET
  7. GET non-existent 404: MET
  8. PATCH partial update 200: MET
  9. PATCH non-existent 404: MET
  10. DELETE 204 then not retrievable: MET
  11. DELETE non-existent 404: MET
  12. Router registered in create_app(): MET
  13. Business logic in core/project.py: MET
  14. All responses use Pydantic response_model: MET
- Follow-up issues created: none needed
- VERDICT: ACCEPT
