# 142 — Agent-Task Binding: link sessions to pipeline steps

## Problem

When the orchestrator spawns an agent session to work on a task, there is no link between them. The app cannot tell which session is working on which task at which pipeline step. When the session ends, results do not flow back to the task. The UI cannot show "Session X is grooming Task #5".

## Dependencies

- #05 Session CRUD API (done)
- #06 Task Queue API (done)
- #22 Orchestrator Mode (done)

## Scope

Backend-only. This issue adds `task_id` and `pipeline_step` columns to the `Session` model, wires them through the session creation flow, updates the orchestrator to set them when spawning agent sessions, and adds a query endpoint to find sessions by task.

No frontend/UI changes are in scope. The "Pipeline UI can show which agent is working on which task" from the original vision is out of scope -- that is a frontend issue that depends on this backend work.

---

## User Stories

### Story: Orchestrator spawns an agent and records the binding
1. The orchestrator picks a task from the backlog
2. The orchestrator transitions the task to "grooming"
3. The orchestrator calls `create_session` with `task_id=<task_uuid>` and `pipeline_step="grooming"`
4. A new Session row is created in the DB with `task_id` and `pipeline_step` populated
5. The Session's `task_id` is a FK to the `tasks` table
6. The Session's `pipeline_step` is a string matching one of the known pipeline steps

### Story: API consumer queries sessions by task
1. A client sends `GET /api/sessions?task_id=<uuid>`
2. The API returns all sessions that have `task_id` matching the given UUID
3. Each returned session includes `task_id` and `pipeline_step` in the response body
4. If no sessions match, the API returns an empty list

### Story: Session response includes task binding fields
1. A client creates a session via `POST /api/projects/{pid}/sessions` with `task_id` and `pipeline_step` in the body
2. The response (201) includes `task_id` and `pipeline_step` fields
3. A client fetches `GET /api/sessions/{id}` -- the response includes `task_id` and `pipeline_step`
4. A client lists sessions via `GET /api/projects/{pid}/sessions` -- each session in the list includes `task_id` and `pipeline_step`

---

## Acceptance Criteria

- [ ] `Session` model has a `task_id` column: `PortableUUID`, FK to `tasks.id`, nullable
- [ ] `Session` model has a `pipeline_step` column: `Unicode(50)`, nullable
- [ ] `SessionCreate` schema accepts optional `task_id: uuid.UUID | None` and `pipeline_step: str | None`
- [ ] `SessionRead` schema includes `task_id: uuid.UUID | None` and `pipeline_step: str | None`
- [ ] `create_session()` in `core/session.py` accepts `task_id` and `pipeline_step` kwargs and persists them
- [ ] `create_session()` validates that `task_id` references an existing Task (raises appropriate error if not)
- [ ] `pipeline_step` values are validated against the known set: `grooming`, `implementing`, `testing`, `accepting` (plus `None`)
- [ ] `OrchestratorService._default_spawn_and_run()` passes `task_id` and `step` when creating child sessions
- [ ] `GET /api/sessions?task_id=<uuid>` query parameter filters sessions by task_id (new flat endpoint or query param on existing list endpoint)
- [ ] Alembic migration adds the two new columns to the `sessions` table
- [ ] All existing tests continue to pass (no regressions)
- [ ] `uv run pytest tests/ -v` passes with 6+ new tests covering the binding feature
- [ ] `uv run ruff check` is clean

---

## Technical Notes

### Model changes (`backend/codehive/db/models.py`)

Add to the `Session` class:

```python
task_id: Mapped[uuid.UUID | None] = mapped_column(
    PortableUUID, ForeignKey("tasks.id"), nullable=True
)
pipeline_step: Mapped[str | None] = mapped_column(Unicode(50), nullable=True)
```

Add a `relationship` from `Session` to `Task` (and the back-reference on `Task` if desired). Note: `Session` already has a `tasks` relationship (one-to-many: a session owns tasks). The new `task_id` is the reverse: which task is this session working ON. Name it carefully to avoid collision -- e.g., `bound_task` on Session, `agent_sessions` on Task.

### Schema changes (`backend/codehive/api/schemas/session.py`)

- `SessionCreate`: add `task_id: uuid.UUID | None = None` and `pipeline_step: str | None = None`
- `SessionRead`: add `task_id: uuid.UUID | None` and `pipeline_step: str | None`
- Add a `pipeline_step` validator that checks against `VALID_PIPELINE_STEPS = {"grooming", "implementing", "testing", "accepting"}`

### Service changes (`backend/codehive/core/session.py`)

- `create_session()`: add `task_id` and `pipeline_step` params, validate task exists if provided
- Add a `TaskNotFoundError` exception class (or reuse pattern from `IssueNotFoundError`)

### Orchestrator changes (`backend/codehive/core/orchestrator_service.py`)

- `_default_spawn_and_run()`: pass `task_id=task_id` and `pipeline_step=step` when calling `create_db_session()`

### API route changes (`backend/codehive/api/routes/sessions.py`)

- `create_session_endpoint()`: pass `task_id` and `pipeline_step` from body to `create_session()`
- Add a `task_id` query parameter to the session list endpoint (or add a new flat `GET /api/sessions?task_id=X` endpoint)

### Migration

- Create an Alembic migration that adds `task_id` (UUID, FK to tasks.id, nullable) and `pipeline_step` (VARCHAR(50), nullable) to `sessions`.

---

## Test Scenarios

### Unit: Session model with task binding
- Create a Session with `task_id` and `pipeline_step` set; verify both persist and are readable
- Create a Session without `task_id` and `pipeline_step`; verify they default to None
- Verify FK constraint: creating a Session with a non-existent `task_id` raises an error

### Unit: create_session service
- Call `create_session(task_id=valid_task_id, pipeline_step="grooming")`; verify session is created with correct values
- Call `create_session(task_id=invalid_uuid)` -- verify `TaskNotFoundError` is raised
- Call `create_session(pipeline_step="invalid_step")` -- verify validation error is raised
- Call `create_session()` with no `task_id` or `pipeline_step` -- verify backward compatibility (both None)

### Unit: Schema validation
- `SessionCreate(task_id=uuid, pipeline_step="grooming")` -- valid
- `SessionCreate(pipeline_step="unknown")` -- validation error
- `SessionRead` round-trips `task_id` and `pipeline_step` correctly from ORM model

### Integration: API endpoints
- `POST /api/projects/{pid}/sessions` with `task_id` and `pipeline_step` in body -- returns 201 with both fields
- `POST /api/projects/{pid}/sessions` with invalid `task_id` -- returns 404
- `POST /api/projects/{pid}/sessions` with invalid `pipeline_step` -- returns 422
- `GET /api/sessions/{id}` -- response includes `task_id` and `pipeline_step`
- `GET /api/sessions?task_id=<uuid>` -- returns only sessions bound to that task
- `GET /api/sessions?task_id=<uuid>` with no matches -- returns empty list

### Integration: Orchestrator binding
- Mock `_spawn_and_run` on OrchestratorService, verify that `_default_spawn_and_run` calls `create_session` with `task_id` and the correct `pipeline_step` for each step

## Log

### [SWE] 2026-03-28 12:00
- Added `task_id` (FK to tasks.id, nullable) and `pipeline_step` (Unicode(50), nullable) columns to Session model
- Added `bound_task` relationship on Session and `agent_sessions` back-reference on Task, with explicit `foreign_keys` to avoid ambiguity from circular FK
- Used `use_alter=True` on the Session.task_id FK to break circular dependency for DDL ordering
- Added `VALID_PIPELINE_STEPS` constant and validator to SessionCreate schema
- Added `task_id` and `pipeline_step` fields to both SessionCreate and SessionRead schemas
- Updated `create_session()` to accept and validate `task_id` and `pipeline_step`, with `TaskNotFoundError` and `InvalidPipelineStepError` exceptions
- Added `list_sessions_by_task()` service function
- Updated `create_session_endpoint` to pass task_id/pipeline_step from body
- Added `GET /api/sessions?task_id=<uuid>` flat endpoint for filtering sessions by task
- Updated `_default_spawn_and_run()` in OrchestratorService to pass `task_id` and `pipeline_step` when creating child sessions
- No Alembic migration (project uses create_all, no alembic setup exists)
- Files modified: backend/codehive/db/models.py, backend/codehive/api/schemas/session.py, backend/codehive/core/session.py, backend/codehive/api/routes/sessions.py, backend/codehive/core/orchestrator_service.py
- Files added: backend/tests/test_agent_task_binding.py
- Tests added: 19 new tests (4 schema, 4 service, 2 list_by_task, 7 API, 2 orchestrator)
- Build results: 106 tests pass (87 existing + 19 new), 0 fail, ruff clean
- Known limitations: No Alembic migration generated (no alembic directory in project)

### [QA] 2026-03-28 12:30
- Tests: 2265 passed, 0 failed, 3 skipped (full suite); 19 new binding tests all pass
- Ruff check: clean (All checks passed!)
- Ruff format: clean (282 files already formatted)

Acceptance criteria:
1. Session model has task_id column (PortableUUID, FK to tasks.id, nullable): PASS - models.py line 169-171
2. Session model has pipeline_step column (Unicode(50), nullable): PASS - models.py line 172
3. SessionCreate schema accepts optional task_id and pipeline_step: PASS - schemas/session.py lines 49-50
4. SessionRead schema includes task_id and pipeline_step: PASS - schemas/session.py lines 117-118
5. create_session() accepts task_id and pipeline_step and persists them: PASS - session.py lines 103-104, 148
6. create_session() validates task_id references existing Task (TaskNotFoundError): PASS - session.py lines 133-136, test confirms
7. pipeline_step validated against known set (grooming, implementing, testing, accepting): PASS - schema validator + service-level check
8. OrchestratorService._default_spawn_and_run() passes task_id and step: PASS - orchestrator_service.py diff confirmed
9. GET /api/sessions?task_id=<uuid> filters sessions by task_id: PASS - routes/sessions.py lines 110-117, test confirms
10. Alembic migration: N/A - project uses create_all, no alembic directory exists. Acceptable.
11. All existing tests continue to pass: PASS - 2265 passed, 0 failed
12. 6+ new tests: PASS - 19 new tests covering schema, service, list_by_task, API, and orchestrator
13. Ruff check clean: PASS

- bound_task relationship avoids collision with existing tasks relationship: PASS - models.py lines 174-178 use explicit foreign_keys
- VERDICT: PASS

### [PM] 2026-03-28 13:00
- Reviewed diff: 5 backend files changed (models.py, session.py, sessions.py routes, session.py schema, orchestrator_service.py) + 1 new test file
- Results verified: real data present -- 19 tests exercise all binding paths (schema, service, API, orchestrator)
- Acceptance criteria: all met (13/13); Alembic migration AC is N/A since project uses create_all with no alembic directory
- Model design verified: use_alter=True on circular FK is correct; bound_task/agent_sessions relationship pair is cleanly separated from existing tasks/session pair via explicit foreign_keys
- Follow-up issues created: none needed
- VERDICT: ACCEPT
