# 06: Task Queue API

## Description
REST API endpoints for managing the ToDo/task queue within a session. Tasks are the operational work items that an agent processes -- each session has an ordered queue of tasks. This issue covers CRUD endpoints, status transitions, reordering, and the "next task" query. Follows the same patterns established in issues #04 (Project CRUD) and #05 (Session CRUD): thin route handlers, Pydantic schemas, business logic in core layer, async SQLAlchemy with dependency injection.

## Scope
- `backend/codehive/api/routes/tasks.py` -- Task CRUD + status transition + reorder endpoints
- `backend/codehive/api/schemas/task.py` -- Pydantic request/response models
- `backend/codehive/core/task_queue.py` -- Task queue business logic (DB queries, ordering, status transitions, dependency checking)
- `backend/codehive/api/app.py` -- updated to register the tasks routers
- `backend/tests/test_tasks.py` -- API tests (CRUD happy path + error cases + status transitions + reorder + next task)

## Endpoints

Tasks use two URL prefixes: session-scoped for creation/listing, and flat for operations on individual tasks.

| Method | Path | Description | Status Code |
|--------|------|-------------|-------------|
| POST | `/api/sessions/{session_id}/tasks` | Create a task in a session | 201 (404 if session not found) |
| GET | `/api/sessions/{session_id}/tasks` | List tasks for a session (ordered by priority desc, created_at asc) | 200 (404 if session not found) |
| GET | `/api/sessions/{session_id}/tasks/next` | Get the next actionable task (highest priority pending task with no unmet dependencies) | 200 with task or 204 if none available (404 if session not found) |
| GET | `/api/tasks/{id}` | Get a single task | 200 (404 if not found) |
| PATCH | `/api/tasks/{id}` | Update task fields (title, instructions, priority, mode, depends_on) | 200 (404 if not found) |
| DELETE | `/api/tasks/{id}` | Delete a task | 204 (404 if not found) |
| POST | `/api/tasks/{id}/transition` | Transition task status (body: `{"status": "running"}`) | 200 (404 if not found, 409 if invalid transition) |
| POST | `/api/sessions/{session_id}/tasks/reorder` | Reorder tasks (body: list of `{"id": uuid, "priority": int}`) | 200 (404 if session not found, 422 if task IDs invalid) |

### Request/Response Schemas

**TaskCreate** (POST body):
- `title`: str (required, max 500 chars)
- `instructions`: str | null (optional)
- `priority`: int (optional, default 0 -- higher = runs first)
- `depends_on`: UUID | null (optional -- FK to another task in the same session)
- `mode`: str (optional, default "auto" -- "auto" or "manual")
- `created_by`: str (optional, default "user" -- "user" or "agent")

Note: `session_id` comes from the URL path, not the request body. `status` is always "pending" on creation.

**TaskUpdate** (PATCH body -- all fields optional):
- `title`: str | null
- `instructions`: str | null
- `priority`: int | null
- `mode`: str | null
- `depends_on`: UUID | null

Note: `status` is NOT updatable via PATCH. Status changes happen only through the dedicated `/transition` endpoint.

**TaskStatusTransition** (POST body for `/transition`):
- `status`: str (required -- the target status)

**TaskReorderItem** (items in reorder list):
- `id`: UUID (required)
- `priority`: int (required)

**TaskRead** (response):
- `id`: UUID
- `session_id`: UUID
- `title`: str
- `instructions`: str | null
- `status`: str
- `priority`: int
- `depends_on`: UUID | null
- `mode`: str
- `created_by`: str
- `created_at`: datetime

## Task Statuses and State Machine

Valid statuses: `pending`, `running`, `blocked`, `done`, `failed`, `skipped`

New tasks are created with status `pending`.

### Allowed Transitions

| From | To | Description |
|------|----|-------------|
| pending | running | Task starts execution |
| pending | blocked | Dependency not met or manual block |
| pending | skipped | User or agent decides to skip |
| running | done | Task completed successfully |
| running | failed | Task execution failed |
| running | blocked | Task encountered a blocker |
| blocked | pending | Blocker resolved, task re-queued |
| failed | pending | Retry -- task re-queued for another attempt |

Any transition not in this table returns 409 Conflict. Terminal states (`done`, `skipped`) cannot transition to anything.

### Next Task Logic

`GET /api/sessions/{session_id}/tasks/next` returns the highest-priority `pending` task whose `depends_on` is either null or points to a task with status `done`. If no such task exists, return 204 No Content.

## Design Decisions

- **Session must exist.** POST `/api/sessions/{session_id}/tasks` requires a valid session_id. Return 404 if the session does not exist.
- **depends_on is validated** if provided on create or update. It must reference an existing task in the same session. Return 404 with descriptive message if it references a non-existent task, or 422 if the referenced task belongs to a different session.
- **No cascading deletes for depends_on.** Deleting a task that other tasks depend on is allowed -- the dependent tasks simply have a dangling `depends_on` reference (treated as "no dependency" for next-task logic). This keeps things simple for now.
- **Reorder is a bulk priority update.** The reorder endpoint receives a list of `{id, priority}` pairs and updates them in a single transaction. Task IDs must all belong to the given session -- return 422 if any ID is not found or belongs to a different session. It does not need to include all tasks -- only the ones being reordered.
- **Async SQLAlchemy** throughout. Same dependency injection pattern as sessions.
- **Tests use SQLite in-memory** via `aiosqlite` -- no Docker needed. Reuse the same fixture pattern from `test_sessions.py` (db_session, workspace, project, session, client).
- **Business logic in core layer.** Routes are thin HTTP translators; all DB queries and validation logic live in `core/task_queue.py`.

## Dependencies
- Depends on: #05 (Session CRUD API -- DONE) -- needs session endpoints, patterns, and a session to attach tasks to
- Depends on: #03 (Database models -- DONE) -- Task model already exists with all required columns

## Acceptance Criteria

- [ ] `uv run pytest backend/tests/test_tasks.py -v` passes with 25+ tests
- [ ] POST `/api/sessions/{session_id}/tasks` with valid payload returns 201 and the created task with `id`, `status` = "pending", `priority` = 0 (default), and `created_at`
- [ ] POST `/api/sessions/{session_id}/tasks` with non-existent `session_id` returns 404
- [ ] POST `/api/sessions/{session_id}/tasks` with missing required `title` field returns 422
- [ ] POST `/api/sessions/{session_id}/tasks` with non-existent `depends_on` task ID returns 404
- [ ] POST `/api/sessions/{session_id}/tasks` with `depends_on` pointing to a task in a different session returns 422
- [ ] GET `/api/sessions/{session_id}/tasks` returns 200 with a JSON list of tasks ordered by priority desc, then created_at asc
- [ ] GET `/api/sessions/{session_id}/tasks` with non-existent session returns 404
- [ ] GET `/api/sessions/{session_id}/tasks` for a session with no tasks returns 200 with empty list
- [ ] GET `/api/sessions/{session_id}/tasks/next` returns 200 with the highest-priority pending task that has no unmet dependencies
- [ ] GET `/api/sessions/{session_id}/tasks/next` returns 204 when no actionable tasks exist (all done/blocked/running)
- [ ] GET `/api/sessions/{session_id}/tasks/next` skips pending tasks whose `depends_on` task is not `done`
- [ ] GET `/api/sessions/{session_id}/tasks/next` with non-existent session returns 404
- [ ] GET `/api/tasks/{id}` with valid ID returns 200 with full task data
- [ ] GET `/api/tasks/{id}` with non-existent ID returns 404
- [ ] PATCH `/api/tasks/{id}` with partial payload updates only the provided fields and returns 200
- [ ] PATCH `/api/tasks/{id}` with non-existent ID returns 404
- [ ] DELETE `/api/tasks/{id}` with valid ID returns 204 and the task is no longer retrievable
- [ ] DELETE `/api/tasks/{id}` with non-existent ID returns 404
- [ ] POST `/api/tasks/{id}/transition` with `{"status": "running"}` from `pending` returns 200 with updated status
- [ ] POST `/api/tasks/{id}/transition` with `{"status": "done"}` from `pending` returns 409 (invalid transition)
- [ ] POST `/api/tasks/{id}/transition` from terminal state (`done`, `skipped`) returns 409
- [ ] POST `/api/tasks/{id}/transition` with non-existent ID returns 404
- [ ] POST `/api/sessions/{session_id}/tasks/reorder` with valid task ID/priority pairs returns 200 and priorities are updated
- [ ] POST `/api/sessions/{session_id}/tasks/reorder` with a task ID from a different session returns 422
- [ ] POST `/api/sessions/{session_id}/tasks/reorder` with non-existent session returns 404
- [ ] The tasks routers are registered in `create_app()` so the server includes these routes
- [ ] Business logic lives in `backend/codehive/core/task_queue.py`, not directly in route handlers
- [ ] All responses use Pydantic `response_model` for serialization
- [ ] Full test suite still passes: `uv run pytest backend/tests/ -v` (no regressions)

## Test Scenarios

### Unit: Core task queue operations (test with async SQLite)
- `create_task` persists a task with status "pending" and returns it with generated `id` and `created_at`
- `create_task` with explicit priority, instructions, mode, created_by stores them correctly
- `create_task` with non-existent session_id raises SessionNotFoundError
- `create_task` with non-existent depends_on raises TaskNotFoundError
- `create_task` with depends_on referencing a task in a different session raises InvalidDependencyError
- `list_tasks` for a session returns tasks ordered by priority desc, created_at asc
- `list_tasks` for empty session returns empty list
- `list_tasks` for non-existent session raises SessionNotFoundError
- `get_task` with valid ID returns the task
- `get_task` with non-existent ID returns None
- `update_task` modifies only specified fields (e.g. priority), leaves others unchanged
- `update_task` with non-existent ID raises TaskNotFoundError
- `delete_task` removes the task from the database
- `delete_task` with non-existent ID raises TaskNotFoundError
- `transition_task` from pending to running succeeds
- `transition_task` from pending to blocked succeeds
- `transition_task` from pending to skipped succeeds
- `transition_task` from running to done succeeds
- `transition_task` from running to failed succeeds
- `transition_task` from running to blocked succeeds
- `transition_task` from blocked to pending succeeds
- `transition_task` from failed to pending succeeds (retry)
- `transition_task` from done to anything raises InvalidStatusTransitionError
- `transition_task` from skipped to anything raises InvalidStatusTransitionError
- `transition_task` from pending to done raises InvalidStatusTransitionError (must go through running)
- `transition_task` with non-existent ID raises TaskNotFoundError
- `get_next_task` returns highest-priority pending task with no unmet dependencies
- `get_next_task` skips a pending task whose depends_on points to a non-done task
- `get_next_task` returns a pending task whose depends_on points to a done task
- `get_next_task` returns None when all tasks are done/running/blocked
- `get_next_task` with non-existent session raises SessionNotFoundError
- `reorder_tasks` updates priorities for the given task IDs
- `reorder_tasks` with a task ID from another session raises InvalidDependencyError
- `reorder_tasks` with non-existent session raises SessionNotFoundError

### Integration: API endpoints (via FastAPI TestClient)
- POST /api/sessions/{session_id}/tasks with valid body -> 201, response matches TaskRead schema, status is "pending"
- POST /api/sessions/{session_id}/tasks with all optional fields -> 201, all fields stored
- POST /api/sessions/{session_id}/tasks missing title -> 422 validation error
- POST /api/sessions/{bad-uuid}/tasks -> 404
- POST /api/sessions/{session_id}/tasks with bad depends_on -> 404
- GET /api/sessions/{session_id}/tasks -> 200, returns ordered list (test with 0 and 3+ tasks at different priorities)
- GET /api/sessions/{bad-uuid}/tasks -> 404
- GET /api/sessions/{session_id}/tasks/next -> 200 with correct task, or 204 when none available
- GET /api/sessions/{session_id}/tasks/next with dependency chain -> correct task selected
- GET /api/tasks/{id} -> 200 with correct data
- GET /api/tasks/{unknown-uuid} -> 404
- PATCH /api/tasks/{id} with `{"priority": 10}` -> 200, only priority changed
- PATCH /api/tasks/{unknown-uuid} -> 404
- DELETE /api/tasks/{id} -> 204, subsequent GET -> 404
- DELETE /api/tasks/{unknown-uuid} -> 404
- POST /api/tasks/{id}/transition with `{"status": "running"}` from pending -> 200, status is "running"
- POST /api/tasks/{id}/transition with `{"status": "done"}` from pending -> 409
- POST /api/tasks/{id}/transition from done state -> 409
- POST /api/tasks/{unknown-uuid}/transition -> 404
- POST /api/sessions/{session_id}/tasks/reorder with valid pairs -> 200, priorities updated (verified by GET list)
- POST /api/sessions/{session_id}/tasks/reorder with cross-session task -> 422
- POST /api/sessions/{bad-uuid}/tasks/reorder -> 404

## Log

### [SWE] 2026-03-15 12:00
- Implemented Task Queue API following Session CRUD patterns (thin routes, Pydantic schemas, core business logic)
- Created Pydantic schemas: TaskCreate, TaskUpdate, TaskStatusTransition, TaskReorderItem, TaskRead
- Implemented core business logic with full state machine (6 statuses, 8 allowed transitions)
- Implemented next-task logic: highest-priority pending task with no unmet dependencies
- Implemented bulk reorder endpoint with cross-session validation
- Registered session_tasks_router and tasks_router in create_app()
- Files created: backend/codehive/api/schemas/task.py, backend/codehive/core/task_queue.py, backend/codehive/api/routes/tasks.py, backend/tests/test_tasks.py
- Files modified: backend/codehive/api/app.py
- Tests added: 62 tests (37 unit core tests + 25 integration API tests)
- Build results: 233 tests pass (full suite), 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-15 12:30
- Tests: 233 passed (full suite), 0 failed; 62 in test_tasks.py
- Ruff: clean (check + format)
- Acceptance criteria:
  1. 25+ tests in test_tasks.py: PASS (62 tests)
  2. POST create returns 201 with id, status=pending, priority=0, created_at: PASS
  3. POST with non-existent session_id returns 404: PASS
  4. POST with missing title returns 422: PASS
  5. POST with non-existent depends_on returns 404: PASS
  6. POST with depends_on in different session returns 422: PASS
  7. GET list returns 200 ordered by priority desc, created_at asc: PASS
  8. GET list with non-existent session returns 404: PASS
  9. GET list for empty session returns 200 with empty list: PASS
  10. GET next returns highest-priority pending task with no unmet deps: PASS
  11. GET next returns 204 when no actionable tasks: PASS
  12. GET next skips pending tasks whose depends_on is not done: PASS
  13. GET next with non-existent session returns 404: PASS
  14. GET task by id returns 200: PASS
  15. GET task with non-existent id returns 404: PASS
  16. PATCH with partial payload updates only provided fields: PASS
  17. PATCH with non-existent id returns 404: PASS
  18. DELETE returns 204 and task not retrievable: PASS
  19. DELETE with non-existent id returns 404: PASS
  20. POST transition pending->running returns 200: PASS
  21. POST transition pending->done returns 409: PASS
  22. POST transition from terminal state returns 409: PASS
  23. POST transition with non-existent id returns 404: PASS
  24. POST reorder with valid pairs returns 200: PASS
  25. POST reorder with cross-session task returns 422: PASS
  26. POST reorder with non-existent session returns 404: PASS
  27. Routers registered in create_app(): PASS
  28. Business logic in core/task_queue.py: PASS
  29. All responses use Pydantic response_model: PASS
  30. Full test suite passes (no regressions): PASS
- Note: app.py also registers events_router and ws_router from issue #07 (cross-contamination from parallel work, non-blocking)
- VERDICT: PASS

### [PM] 2026-03-15 13:00
- Reviewed diff: 5 tracked files changed + 4 new task files (routes, schemas, core, tests)
- Results verified: real data present -- 62 tests executed and passing, full suite 233 passed
- Code quality: routes are thin HTTP translators, all business logic in core/task_queue.py, Pydantic response_model on all endpoints, state machine matches spec exactly (6 statuses, 8 transitions), next-task dependency logic correct including dangling reference handling
- Acceptance criteria: all 30 met
  - 8 endpoints implemented (POST create, GET list, GET next, GET single, PATCH, DELETE, POST transition, POST reorder)
  - Full state machine with correct allowed/disallowed transitions
  - Dependency-aware next-task query working correctly
  - Bulk reorder with cross-session validation
  - 62 tests (37 unit + 25 integration), all meaningful
- Note: app.py includes events_router and ws_router from parallel issue #07 work -- non-blocking, no impact on task functionality
- Follow-up issues created: none needed
- VERDICT: ACCEPT
