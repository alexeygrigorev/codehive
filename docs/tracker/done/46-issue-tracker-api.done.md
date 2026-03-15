# 46: Issue Tracker API

## Description
Implement the project-level issue tracker API. Issues are long-lived project tasks (like GitHub Issues) that can have multiple sessions working on them. Support CRUD operations and linking sessions to issues.

## Scope
- `backend/codehive/api/schemas/issue.py` -- Pydantic request/response schemas (IssueCreate, IssueUpdate, IssueRead, IssueReadWithSessions)
- `backend/codehive/core/issues.py` -- Issue business logic (create, list, get, update, delete, link session)
- `backend/codehive/api/routes/issues.py` -- Issue CRUD endpoints (project-scoped and flat routers)
- `backend/codehive/api/app.py` -- Register issue routers
- `backend/tests/test_issues.py` -- Unit and integration tests

## Endpoints
- `POST /api/projects/{project_id}/issues` -- Create issue (201)
- `GET /api/projects/{project_id}/issues` -- List issues for project, with optional `?status=open` query filter (200)
- `GET /api/issues/{issue_id}` -- Get single issue with linked sessions list (200)
- `PATCH /api/issues/{issue_id}` -- Update issue title, description, or status (200)
- `DELETE /api/issues/{issue_id}` -- Delete issue; fail with 409 if sessions are linked (204)
- `POST /api/issues/{issue_id}/link-session/{session_id}` -- Link an existing session to an issue by setting session.issue_id (200)

## Data Model Reference (already exists in #03)
The `Issue` model in `backend/codehive/db/models.py` has: `id` (UUID PK), `project_id` (FK to projects), `title` (str), `description` (str, nullable), `status` (str, default "open"), `github_issue_id` (int, nullable), `created_at`. It has a `sessions` relationship (list of Session where session.issue_id == issue.id).

## Implementation Notes

### Schemas (`api/schemas/issue.py`)
- `IssueCreate`: `title` (required, max_length=500), `description` (optional)
- `IssueUpdate`: `title` (optional), `description` (optional), `status` (optional, must be one of: "open", "in_progress", "closed")
- `IssueRead`: all fields from the model (id, project_id, title, description, status, github_issue_id, created_at)
- `IssueReadWithSessions`: extends IssueRead with `sessions: list[SessionRead]` for the GET single-issue endpoint

### Business Logic (`core/issues.py`)
Follow the same pattern as `core/project.py`:
- Custom exceptions: `IssueNotFoundError`, `ProjectNotFoundError` (reuse from core.project or define locally), `IssueHasLinkedSessionsError`, `SessionNotFoundError`
- `create_issue(db, project_id, title, description)` -- verify project exists, create Issue row
- `list_issues(db, project_id, status=None)` -- verify project exists, query with optional status filter
- `get_issue(db, issue_id)` -- return Issue or None; eagerly load sessions relationship
- `update_issue(db, issue_id, **fields)` -- partial update, validate status values
- `delete_issue(db, issue_id)` -- check for linked sessions, raise IssueHasLinkedSessionsError if any
- `link_session_to_issue(db, issue_id, session_id)` -- verify both exist, set session.issue_id = issue_id, commit

### Routes (`api/routes/issues.py`)
Use dual-router pattern matching sessions:
- `project_issues_router` with prefix `/api/projects/{project_id}/issues` for create and list
- `issues_router` with prefix `/api/issues` for get, update, delete, and link-session

### Router Registration (`api/app.py`)
Add `project_issues_router` and `issues_router` to `create_app()`.

### Valid Issue Statuses
- `open` (default)
- `in_progress`
- `closed`

## Dependencies
- #03 (Database models) -- Issue model and Session.issue_id FK already exist
- #04 (Project CRUD) -- projects must exist before creating issues; reuses project patterns

## Acceptance Criteria

- [x] `POST /api/projects/{project_id}/issues` with `{"title": "Bug"}` returns 201 with an `id`, `project_id`, `title`, `status` of "open", and `created_at`
- [x] `POST /api/projects/{project_id}/issues` with a non-existent project_id returns 404
- [x] `POST /api/projects/{project_id}/issues` without `title` returns 422
- [x] `GET /api/projects/{project_id}/issues` returns 200 with a list of issues for that project
- [x] `GET /api/projects/{project_id}/issues?status=open` returns only issues with status "open"
- [x] `GET /api/projects/{project_id}/issues` with a non-existent project_id returns 404
- [x] `GET /api/issues/{issue_id}` returns 200 with issue data including a `sessions` list
- [x] `GET /api/issues/{issue_id}` with a non-existent ID returns 404
- [x] `PATCH /api/issues/{issue_id}` with `{"status": "closed"}` returns 200 with updated status
- [x] `PATCH /api/issues/{issue_id}` with partial fields updates only those fields
- [x] `PATCH /api/issues/{issue_id}` with a non-existent ID returns 404
- [x] `DELETE /api/issues/{issue_id}` returns 204 and the issue is no longer retrievable
- [x] `DELETE /api/issues/{issue_id}` with a non-existent ID returns 404
- [x] `DELETE /api/issues/{issue_id}` when sessions are linked returns 409
- [x] `POST /api/issues/{issue_id}/link-session/{session_id}` sets `session.issue_id` and returns 200
- [x] `POST /api/issues/{issue_id}/link-session/{session_id}` with non-existent issue or session returns 404
- [x] Issue routers are registered in `create_app()` and accessible
- [x] `uv run pytest backend/tests/test_issues.py -v` passes with 20+ tests covering all the above

## Test Scenarios

### Unit: Core issue operations (`core/issues.py`)
- `create_issue` with valid project_id persists issue with status "open"
- `create_issue` with non-existent project_id raises ProjectNotFoundError
- `list_issues` returns empty list for project with no issues
- `list_issues` returns multiple issues for a project
- `list_issues` with `status="open"` filters correctly (returns only matching issues)
- `get_issue` returns issue with sessions relationship loaded
- `get_issue` with non-existent ID returns None
- `update_issue` changes only specified fields
- `update_issue` with non-existent ID raises IssueNotFoundError
- `delete_issue` removes the issue from DB
- `delete_issue` with non-existent ID raises IssueNotFoundError
- `delete_issue` when sessions are linked raises IssueHasLinkedSessionsError
- `link_session_to_issue` sets session.issue_id correctly
- `link_session_to_issue` with non-existent issue raises IssueNotFoundError
- `link_session_to_issue` with non-existent session raises SessionNotFoundError

### Integration: API endpoints via AsyncClient
- POST create issue returns 201 with correct response body
- POST create issue with missing title returns 422
- POST create issue with bad project_id returns 404
- GET list issues returns 200 with empty list, then with created issues
- GET list issues with status filter returns only matching issues
- GET list issues with bad project_id returns 404
- GET single issue returns 200 with sessions list included
- GET single issue with bad ID returns 404
- PATCH update issue returns 200 with updated fields
- PATCH update issue with bad ID returns 404
- DELETE issue returns 204 then GET returns 404
- DELETE issue with bad ID returns 404
- DELETE issue with linked sessions returns 409
- POST link-session returns 200 and session.issue_id is set
- POST link-session with bad issue or session ID returns 404

## Log

### [SWE] 2026-03-15 10:00
- Implemented Issue Tracker API with full CRUD, status filtering, and session linking
- Created Pydantic schemas: IssueCreate, IssueUpdate, IssueRead, IssueReadWithSessions
- Created core business logic with custom exceptions and all 6 operations (create, list, get, update, delete, link_session_to_issue)
- Created dual-router pattern: project_issues_router (POST/GET under /api/projects/{id}/issues) and issues_router (GET/PATCH/DELETE under /api/issues/{id}, plus link-session)
- Registered both routers in create_app()
- GET single issue eagerly loads sessions via selectinload and returns IssueReadWithSessions
- DELETE with linked sessions returns 409
- Files created: backend/codehive/api/schemas/issue.py, backend/codehive/core/issues.py, backend/codehive/api/routes/issues.py
- Files modified: backend/codehive/api/app.py
- Tests added: 36 tests (17 unit core + 19 integration API) covering all acceptance criteria
- Build results: 36 tests pass, 0 fail, ruff clean

### [QA] 2026-03-15 10:30
- Tests: 36 passed, 0 failed (test_issues.py); 544 passed full suite
- Ruff check: clean
- Ruff format: clean
- Acceptance criteria:
  1. POST /api/projects/{project_id}/issues with {"title": "Bug"} returns 201 with id, project_id, title, status "open", created_at: PASS
  2. POST with non-existent project_id returns 404: PASS
  3. POST without title returns 422: PASS
  4. GET /api/projects/{project_id}/issues returns 200 with list: PASS
  5. GET with ?status=open returns only matching issues: PASS
  6. GET with non-existent project_id returns 404: PASS
  7. GET /api/issues/{issue_id} returns 200 with sessions list: PASS
  8. GET /api/issues/{issue_id} with non-existent ID returns 404: PASS
  9. PATCH with {"status": "closed"} returns 200 with updated status: PASS
  10. PATCH with partial fields updates only those fields: PASS
  11. PATCH with non-existent ID returns 404: PASS
  12. DELETE returns 204 and issue no longer retrievable: PASS
  13. DELETE with non-existent ID returns 404: PASS
  14. DELETE when sessions linked returns 409: PASS
  15. POST link-session sets session.issue_id and returns 200: PASS
  16. POST link-session with non-existent issue or session returns 404: PASS
  17. Issue routers registered in create_app() and accessible: PASS
  18. 20+ tests covering all criteria: PASS (36 tests)
- VERDICT: PASS

### [PM] 2026-03-15 11:00
- Reviewed diff: 4 files changed (3 new: core/issues.py, api/routes/issues.py, api/schemas/issue.py; 1 modified: api/app.py) + 1 new test file
- Results verified: real data present -- 36 tests executed and all pass, test output confirms correct HTTP status codes and response bodies for all 6 endpoints
- Code quality: clean separation of concerns (schemas/core/routes), follows existing project patterns (dual-router, custom exceptions, selectinload for eager loading), proper Pydantic v2 usage with ConfigDict and regex validation on status field
- Acceptance criteria: all 18/18 met
- Follow-up issues created: none
- VERDICT: ACCEPT
