# 47: Workspace Management API

## Description
REST API endpoints for creating, listing, reading, updating, and deleting workspaces. Includes Pydantic request/response schemas, a business logic layer, and comprehensive tests using an in-memory SQLite database (no Docker required for tests). Follows the same patterns established in issue #04 (Project CRUD API) and #05 (Session CRUD API).

The workspace is the root-level container that holds all projects, global settings, integrations, secrets config, and the agent role library.

## Scope
- `backend/codehive/api/routes/workspace.py` -- Workspace CRUD endpoints
- `backend/codehive/api/schemas/workspace.py` -- Pydantic models for request/response
- `backend/codehive/core/workspace.py` -- Workspace business logic (DB queries)
- `backend/codehive/api/app.py` -- updated to register the workspace router
- `backend/tests/test_workspace.py` -- API tests (CRUD happy path + error cases)

## Endpoints

All endpoints are mounted under `/api/workspaces`.

| Method | Path | Description | Status Code |
|--------|------|-------------|-------------|
| POST | `/api/workspaces` | Create a workspace | 201 |
| GET | `/api/workspaces` | List all workspaces | 200 |
| GET | `/api/workspaces/{id}` | Get a single workspace with settings | 200 (404 if not found) |
| PATCH | `/api/workspaces/{id}` | Update workspace (name, root_path, settings) | 200 (404 if not found) |
| DELETE | `/api/workspaces/{id}` | Delete a workspace | 204 (404 if not found, 409 if has projects) |
| GET | `/api/workspaces/{id}/projects` | List projects in workspace | 200 (404 if workspace not found) |

### Request/Response Schemas

**WorkspaceCreate** (POST body):
- `name`: str (required, max 255 chars, unique)
- `root_path`: str (required, max 1024 chars)
- `settings`: dict (optional, default `{}`)

**WorkspaceUpdate** (PATCH body -- all fields optional):
- `name`: str | null
- `root_path`: str | null
- `settings`: dict | null

**WorkspaceRead** (response):
- `id`: UUID
- `name`: str
- `root_path`: str
- `settings`: dict
- `created_at`: datetime

**WorkspaceList** (GET /api/workspaces response):
- List of WorkspaceRead objects

## Design Decisions

- **Unique name constraint.** Workspace names are unique (per the DB model). POST /api/workspaces with a duplicate name should return 409 Conflict.
- **No cascading deletes.** DELETE /api/workspaces/{id} should fail with 409 Conflict if the workspace has associated projects. Clean deletion only. This matches the pattern from Project (#04) and Session (#05).
- **settings field is mutable via PATCH.** Unlike projects where `knowledge` is read-only in CRUD, workspace `settings` is directly editable through PATCH (it holds global config like integrations, secrets config references, etc.).
- **GET /api/workspaces/{id}/projects** reuses the existing `list_projects` core logic from `core/project.py` filtered by workspace_id, or implements a simple query in `core/workspace.py`. This avoids duplicating project listing logic.
- **Async SQLAlchemy** throughout. Same dependency injection pattern as projects and sessions.
- **Tests use SQLite in-memory** via `aiosqlite` -- no Docker needed. Reuse the same fixture pattern from `test_projects.py`.
- **Business logic in core layer.** Routes are thin HTTP translators; all DB queries and validation logic live in `core/workspace.py`.

## Dependencies
- Depends on: #03 (Database models -- DONE) -- Workspace model already exists with all required columns
- Depends on: #04 (Project CRUD API -- DONE) -- follows the same patterns, reuses deps.py and test fixtures

## Acceptance Criteria

- [ ] `uv run pytest backend/tests/test_workspace.py -v` passes with 12+ tests
- [ ] POST `/api/workspaces` with valid payload returns 201 and the created workspace with `id`, `settings`, and `created_at`
- [ ] POST `/api/workspaces` with missing required field `name` returns 422
- [ ] POST `/api/workspaces` with missing required field `root_path` returns 422
- [ ] POST `/api/workspaces` with duplicate `name` returns 409 Conflict
- [ ] GET `/api/workspaces` returns 200 with a JSON list of workspaces (empty list when none exist)
- [ ] GET `/api/workspaces/{id}` with valid ID returns 200 with full workspace data including settings
- [ ] GET `/api/workspaces/{id}` with non-existent ID returns 404
- [ ] PATCH `/api/workspaces/{id}` with partial payload updates only the provided fields and returns 200
- [ ] PATCH `/api/workspaces/{id}` with non-existent ID returns 404
- [ ] PATCH `/api/workspaces/{id}` updating `settings` merges or replaces the settings dict and returns updated data
- [ ] DELETE `/api/workspaces/{id}` with valid ID returns 204 and the workspace is no longer retrievable
- [ ] DELETE `/api/workspaces/{id}` with non-existent ID returns 404
- [ ] DELETE `/api/workspaces/{id}` with associated projects returns 409 Conflict
- [ ] GET `/api/workspaces/{id}/projects` returns 200 with a JSON list of projects belonging to that workspace
- [ ] GET `/api/workspaces/{id}/projects` with non-existent workspace ID returns 404
- [ ] The workspace router is registered in `create_app()` so the server includes these routes
- [ ] Business logic lives in `backend/codehive/core/workspace.py`, not directly in route handlers
- [ ] All responses use Pydantic `response_model` for serialization
- [ ] Custom exceptions (WorkspaceNotFoundError, WorkspaceHasDependentsError, WorkspaceDuplicateNameError) follow the same pattern as ProjectNotFoundError and SessionNotFoundError

## Test Scenarios

### Unit: Core workspace operations (test with async SQLite)
- `create_workspace` persists a workspace and returns it with generated `id`, default `settings` = `{}`, and `created_at`
- `create_workspace` with duplicate name raises WorkspaceDuplicateNameError
- `list_workspaces` returns all workspaces
- `list_workspaces` with no workspaces returns empty list
- `get_workspace` with valid ID returns the workspace
- `get_workspace` with non-existent ID returns None or raises WorkspaceNotFoundError
- `update_workspace` modifies only specified fields (e.g. name), leaves others unchanged
- `update_workspace` with non-existent ID raises WorkspaceNotFoundError
- `update_workspace` updating settings replaces/merges the settings JSONB
- `delete_workspace` removes the workspace from the database
- `delete_workspace` with non-existent ID raises WorkspaceNotFoundError
- `delete_workspace` with associated projects raises WorkspaceHasDependentsError
- `list_workspace_projects` returns projects belonging to the workspace
- `list_workspace_projects` with non-existent workspace raises WorkspaceNotFoundError

### Integration: API endpoints (via FastAPI TestClient)
- POST /api/workspaces with valid body -> 201, response matches WorkspaceRead schema with id, settings, created_at
- POST /api/workspaces missing `name` -> 422 validation error
- POST /api/workspaces missing `root_path` -> 422 validation error
- POST /api/workspaces with duplicate name -> 409 Conflict
- GET /api/workspaces -> 200, returns list (test with 0 and 2+ workspaces)
- GET /api/workspaces/{id} -> 200 with correct data including settings
- GET /api/workspaces/{unknown-uuid} -> 404
- PATCH /api/workspaces/{id} with `{"name": "updated"}` -> 200, only name changed
- PATCH /api/workspaces/{id} with `{"settings": {"key": "value"}}` -> 200, settings updated
- PATCH /api/workspaces/{unknown-uuid} -> 404
- DELETE /api/workspaces/{id} -> 204, subsequent GET -> 404
- DELETE /api/workspaces/{unknown-uuid} -> 404
- DELETE /api/workspaces/{id} with projects -> 409 Conflict
- GET /api/workspaces/{id}/projects -> 200 with list of projects
- GET /api/workspaces/{id}/projects with no projects -> 200 with empty list
- GET /api/workspaces/{unknown-uuid}/projects -> 404

## Log

### [SWE] 2026-03-15 00:00
- Implemented Workspace CRUD API following the exact same patterns as Project CRUD (#04)
- Created Pydantic schemas (WorkspaceCreate, WorkspaceUpdate, WorkspaceRead)
- Created core business logic with all CRUD operations + list_workspace_projects
- Created thin route handlers translating HTTP to core logic
- Registered workspace router in create_app()
- Custom exceptions: WorkspaceNotFoundError, WorkspaceHasDependentsError, WorkspaceDuplicateNameError
- Files created: backend/codehive/api/schemas/workspace.py, backend/codehive/core/workspace.py, backend/codehive/api/routes/workspace.py
- Files modified: backend/codehive/api/app.py
- Tests added: backend/tests/test_workspace.py -- 33 tests (15 unit core + 18 integration API)
- Build results: 33 tests pass, 0 fail, ruff clean on all workspace files
- Note: pre-existing lint error in sessions.py (unused import) unrelated to this issue

### [QA] 2026-03-15 12:00
- Tests: 33 passed, 0 failed (workspace tests); 598 passed, 0 failed (full suite)
- Ruff check: clean (all workspace files)
- Ruff format: clean (all workspace files)
- Acceptance criteria:
  - 12+ tests: PASS (33 tests)
  - POST /api/workspaces 201 with id, settings, created_at: PASS
  - POST missing name 422: PASS
  - POST missing root_path 422: PASS
  - POST duplicate name 409: PASS
  - GET /api/workspaces 200 with list: PASS
  - GET /api/workspaces/{id} 200 with settings: PASS
  - GET /api/workspaces/{id} non-existent 404: PASS
  - PATCH partial update 200: PASS
  - PATCH non-existent 404: PASS
  - PATCH settings update 200: PASS
  - DELETE 204 and workspace gone: PASS
  - DELETE non-existent 404: PASS
  - DELETE with projects 409: PASS
  - GET /api/workspaces/{id}/projects 200: PASS
  - GET /api/workspaces/{id}/projects non-existent 404: PASS
  - Router registered in create_app(): PASS
  - Business logic in core/workspace.py: PASS
  - All responses use response_model: PASS
  - Custom exceptions follow pattern: PASS
- VERDICT: PASS

### [PM] 2026-03-15 14:30
- Reviewed diff: 4 new files (core/workspace.py, api/routes/workspace.py, api/schemas/workspace.py, tests/test_workspace.py), 1 modified file (api/app.py)
- Results verified: real data present -- 33 tests pass (15 unit core + 18 integration API), ruff clean, all endpoints return correct status codes and response shapes
- Acceptance criteria: all 20/20 met
  - 33 tests pass (criterion requires 12+)
  - POST 201 with id/settings/created_at, 422 for missing fields, 409 for duplicate name
  - GET list 200 (empty and populated), GET by ID 200 with settings, GET nonexistent 404
  - PATCH partial update 200 (unchanged fields preserved), PATCH settings 200, PATCH nonexistent 404
  - DELETE 204 then workspace gone (verified via subsequent GET 404), DELETE nonexistent 404, DELETE with projects 409
  - GET /workspaces/{id}/projects 200 with list, empty list, and nonexistent workspace 404
  - Router registered in create_app(), business logic in core layer, response_model on all routes, custom exceptions follow established pattern
- Code quality: follows project CRUD patterns exactly, thin route handlers, async SQLAlchemy throughout, proper IntegrityError handling for duplicate names on both create and update
- Follow-up issues created: none needed
- VERDICT: ACCEPT
