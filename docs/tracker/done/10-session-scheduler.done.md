# 10: Session Scheduler (Auto-Next + Pending Questions)

## Description
Implement the session scheduler that connects the engine to the task queue: auto-picks the next task when one completes, manages pending questions when the agent encounters non-blocking uncertainties, and integrates the session state machine transitions throughout.

## Scope
- `backend/codehive/core/scheduler.py` -- New module: SessionScheduler class with auto-next, pending question management, and session state machine integration
- `backend/codehive/core/pending_questions.py` -- New module: CRUD operations for PendingQuestion model (create, list, answer, get)
- `backend/codehive/api/routes/questions.py` -- New module: API endpoints for pending questions
- `backend/codehive/api/schemas/question.py` -- New module: Pydantic schemas for question request/response
- `backend/tests/test_scheduler.py` -- Scheduler unit tests
- `backend/tests/test_pending_questions.py` -- Pending questions core + API tests
- `backend/codehive/api/app.py` -- Modified: register questions router

## Behavior

### Auto-next task pickup
1. When a task completes (transitions to `done`), the scheduler checks the session config for `queue_enabled` (default: true).
2. If the queue is enabled, the scheduler calls `get_next_task()` from task_queue to find the next actionable pending task.
3. If a next task exists, the scheduler transitions the session to `executing`, transitions the task to `running`, and calls `engine.start_task()`.
4. If no tasks remain, the scheduler transitions the session to `idle` (all work done) or `completed` if configured to auto-complete.
5. Events are emitted via EventBus for each transition: `task.completed`, `task.started`, `session.status_changed`.

### Pending questions queue
1. When the engine signals a non-blocking question (via a `question.asked` event or a tool call), the scheduler creates a PendingQuestion record.
2. If there are remaining tasks in the queue, the scheduler defers the question and continues with the next task (session stays in `executing`).
3. If there are no remaining tasks, the session enters `waiting_input`.
4. When a user answers a pending question via the API, the answer is stored, the question is marked as answered, and a `question.answered` event is emitted.
5. If the session was in `waiting_input` because all tasks were done and only questions remained, answering the last unanswered question transitions the session back to `idle`.

### Session state machine integration
The scheduler manages these transitions:
- `idle` -> `executing` (when auto-starting next task)
- `executing` -> `executing` (when moving from one task to the next)
- `executing` -> `waiting_input` (when question asked and no tasks remain)
- `executing` -> `idle` (when last task completes and no questions pending)
- `waiting_input` -> `idle` (when last pending question is answered)

The scheduler does NOT own pause/resume -- those remain in `core/session.py`.

## Endpoints

### `GET /api/sessions/{session_id}/questions`
- List pending questions for a session
- Query param: `answered` (optional bool filter, default: return all)
- Response: `200` with list of question objects
- 404 if session not found

### `POST /api/sessions/{session_id}/questions/{question_id}/answer`
- Answer a specific pending question
- Request body: `{ "answer": "string" }`
- Response: `200` with updated question object
- 404 if session or question not found
- 409 if question already answered

## Dependencies
- Depends on: #05 (session CRUD) -- done, #06 (task queue) -- done, #07 (event bus) -- done, #09 (engine adapter) -- done

## Acceptance Criteria

- [ ] `backend/codehive/core/scheduler.py` exists with a `SessionScheduler` class
- [ ] `SessionScheduler.__init__` accepts dependencies: db session factory, EventBus, and an EngineAdapter reference
- [ ] `SessionScheduler.on_task_completed(session_id, task_id)` checks queue_enabled in session config, calls `get_next_task()`, and auto-starts the next task if available
- [ ] When auto-starting the next task, the scheduler transitions the task to `running` and the session to `executing`, emitting `task.started` and `session.status_changed` events via EventBus
- [ ] When no next task is available after a task completes, the session transitions to `idle` and a `session.status_changed` event is emitted
- [ ] `SessionScheduler.on_question_asked(session_id, question_text, context)` creates a PendingQuestion record in the DB
- [ ] If tasks remain in the queue when a question is asked, the scheduler defers the question and continues with the next task (no session state change to `waiting_input`)
- [ ] If no tasks remain when a question is asked, the session transitions to `waiting_input`
- [ ] `backend/codehive/core/pending_questions.py` provides: `create_question(db, session_id, question, context)`, `list_questions(db, session_id, answered=None)`, `answer_question(db, question_id, answer)`, `get_question(db, question_id)`
- [ ] `answer_question` raises an error if the question is already answered
- [ ] Answering the last unanswered question when the session is in `waiting_input` transitions the session back to `idle`
- [ ] `GET /api/sessions/{session_id}/questions` returns 200 with a list of question objects; supports `answered` query filter
- [ ] `POST /api/sessions/{session_id}/questions/{question_id}/answer` accepts `{"answer": "..."}`, returns 200 with the updated question, returns 404 if not found, returns 409 if already answered
- [ ] Questions router is registered in `create_app()` in `api/app.py`
- [ ] `question.asked` and `question.answered` events are emitted via EventBus when questions are created and answered
- [ ] `uv run pytest backend/tests/test_scheduler.py -v` passes with 10+ tests
- [ ] `uv run pytest backend/tests/test_pending_questions.py -v` passes with 8+ tests
- [ ] `uv run pytest backend/tests/ -v` continues to pass (no regressions)

## Test Scenarios

### Unit: Pending Questions CRUD (`test_pending_questions.py`)
- Create a question for a session, verify it persists in DB with `answered=False` and `answer=None`
- List questions for a session, verify ordering by `created_at` ascending
- List questions with `answered=True` filter, verify only answered questions returned
- List questions with `answered=False` filter, verify only unanswered questions returned
- Answer a question, verify `answered=True` and `answer` field is set
- Answer an already-answered question, verify error is raised
- Get question by ID, verify fields; get non-existent ID, verify None/error
- Create question for non-existent session, verify SessionNotFoundError

### Unit: SessionScheduler auto-next (`test_scheduler.py`)
- Complete a task when `queue_enabled=True` and another pending task exists: verify the next task transitions to `running`, session status is `executing`, `task.started` event emitted
- Complete a task when `queue_enabled=True` but no pending tasks remain: verify session transitions to `idle`, `session.status_changed` event emitted
- Complete a task when `queue_enabled=False`: verify no auto-pickup occurs, session transitions to `idle`
- Complete a task when the next pending task has unmet dependencies: verify it is skipped and the scheduler picks the correct next actionable task
- Verify that `engine.start_task()` is called with the correct task_id when auto-starting

### Unit: SessionScheduler pending questions (`test_scheduler.py`)
- Question asked when tasks remain: verify PendingQuestion created, next task auto-started, session stays in `executing`
- Question asked when no tasks remain: verify PendingQuestion created, session transitions to `waiting_input`
- Answer the last unanswered question when session is `waiting_input`: verify session transitions to `idle`
- Answer one of multiple unanswered questions when session is `waiting_input`: verify session stays in `waiting_input`

### Unit: Event emission (`test_scheduler.py`)
- Complete a task and auto-start next: verify EventBus.publish called with `task.completed`, `task.started`, and `session.status_changed` events in order
- Question asked: verify EventBus.publish called with `question.asked` event containing the question text and context
- Question answered: verify EventBus.publish called with `question.answered` event containing the answer

### Integration: API endpoints (`test_pending_questions.py`)
- `POST /api/sessions/{id}/questions/{qid}/answer` with valid answer: returns 200, question shows `answered=True`
- `POST /api/sessions/{id}/questions/{qid}/answer` on already-answered question: returns 409
- `GET /api/sessions/{id}/questions`: returns list of questions for the session
- `GET /api/sessions/{id}/questions?answered=false`: returns only unanswered questions
- `GET /api/sessions/{non_existent_id}/questions`: returns 404

## Log

### [SWE] 2026-03-15 12:00
- Implemented SessionScheduler with auto-next task pickup, pending question management, and session state machine integration
- Implemented PendingQuestion CRUD operations (create, list, answer, get) with proper error handling
- Added API endpoints for listing and answering pending questions with session scoping
- Added Pydantic schemas for question request/response
- Registered questions router in create_app()
- Files created:
  - `backend/codehive/core/scheduler.py` -- SessionScheduler class
  - `backend/codehive/core/pending_questions.py` -- CRUD operations
  - `backend/codehive/api/routes/questions.py` -- API endpoints
  - `backend/codehive/api/schemas/question.py` -- Pydantic schemas
  - `backend/tests/test_scheduler.py` -- 14 tests
  - `backend/tests/test_pending_questions.py` -- 20 tests
- Files modified:
  - `backend/codehive/api/app.py` -- registered questions_router
- Tests added: 34 total (14 scheduler + 20 pending questions)
- Build: 289 tests pass, 0 fail, ruff clean on all changed files
- Known limitations: none

### [QA] 2026-03-15 13:30
- Tests: 34 passed (14 scheduler + 20 pending questions), 0 failed
- Full suite: 289 passed, 0 failed (excluding 2 unrelated test_cli.py failures from issue 11)
- Ruff check: clean on all issue 10 files
- Ruff format: clean on all issue 10 files
- Acceptance criteria:
  1. `scheduler.py` exists with `SessionScheduler` class: PASS
  2. `__init__` accepts db_session_factory, EventBus, EngineAdapter: PASS
  3. `on_task_completed` checks queue_enabled, calls get_next_task, auto-starts: PASS
  4. Auto-start transitions task to running, session to executing, emits task.started and session.status_changed: PASS
  5. No next task after completion transitions session to idle with event: PASS
  6. `on_question_asked` creates PendingQuestion in DB: PASS
  7. Tasks remain when question asked: defers question, continues next task, no waiting_input: PASS
  8. No tasks remain when question asked: session transitions to waiting_input: PASS
  9. pending_questions.py provides create_question, list_questions, answer_question, get_question: PASS
  10. answer_question raises error if already answered: PASS
  11. Answering last unanswered question transitions waiting_input to idle: PASS
  12. GET /api/sessions/{id}/questions returns 200, supports answered filter: PASS
  13. POST answer endpoint returns 200/404/409 correctly: PASS
  14. Questions router registered in create_app(): PASS
  15. question.asked and question.answered events emitted via EventBus: PASS
  16. test_scheduler.py passes with 14 tests (10+ required): PASS
  17. test_pending_questions.py passes with 20 tests (8+ required): PASS
  18. Full test suite passes with no regressions: PASS
- VERDICT: PASS

### [PM] 2026-03-15 14:15
- Reviewed diff: 7 files changed (4 new modules, 2 new test files, 1 modified app.py)
- Results verified: real data present -- 34 tests pass (14 scheduler, 20 pending questions), 289 full suite pass, no regressions
- Acceptance criteria: all 18 met
  1. scheduler.py exists with SessionScheduler class: VERIFIED in source
  2. __init__ accepts db_session_factory, EventBus, EngineAdapter: VERIFIED (lines 32-40)
  3. on_task_completed checks queue_enabled, calls get_next_task, auto-starts next: VERIFIED
  4. Auto-start transitions task to running, session to executing, emits events: VERIFIED
  5. No next task after completion transitions session to idle with event: VERIFIED
  6. on_question_asked creates PendingQuestion in DB: VERIFIED
  7. Tasks remain when question asked: defers, continues next task, no waiting_input: VERIFIED
  8. No tasks remain when question asked: session transitions to waiting_input: VERIFIED
  9. pending_questions.py provides create_question, list_questions, answer_question, get_question: VERIFIED
  10. answer_question raises QuestionAlreadyAnsweredError if already answered: VERIFIED
  11. Answering last unanswered question transitions waiting_input to idle: VERIFIED
  12. GET /api/sessions/{id}/questions returns 200 with list, supports answered query filter: VERIFIED
  13. POST answer endpoint returns 200/404/409 correctly: VERIFIED (including cross-session 404)
  14. Questions router registered in create_app(): VERIFIED in app.py diff
  15. question.asked and question.answered events emitted via EventBus: VERIFIED
  16. test_scheduler.py passes with 14 tests (10+ required): VERIFIED
  17. test_pending_questions.py passes with 20 tests (8+ required): VERIFIED
  18. Full test suite passes with no regressions: VERIFIED (289 passed)
- Code quality: clean, follows project patterns, proper error hierarchy, session-scoped security on API endpoints
- Tests are meaningful: cover CRUD, state machine transitions, event ordering, dependency skipping, cross-session isolation
- Follow-up issues created: none needed
- VERDICT: ACCEPT
