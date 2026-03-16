# 61: Action on Tasks End

## Description
From GitHub issue alexeygrigorev/codehive#1: What to do when tasks end -- continue with creating more tasks, or stop if evening is done.

The scheduler (#10) currently just sets session to `idle` when the ToDo queue empties (see `on_task_completed` in `backend/codehive/core/scheduler.py`, lines 107-117). This issue adds a configurable `queue_empty_action` to the session config so the user can control what happens when the last task completes.

## Scope

### Files to modify
- `backend/codehive/core/scheduler.py` -- replace the hard-coded "transition to idle" in the `else` branch of `on_task_completed` with a dispatch on `config["queue_empty_action"]`
- `backend/codehive/api/schemas/session.py` -- add a `QueueEmptyAction` string enum (`stop`, `continue`, `ask`) and a `SessionConfig` typed-dict or Pydantic model that documents the expected keys in `session.config`
- `backend/codehive/core/session.py` -- validate `queue_empty_action` value on session creation/update (reject unknown values)

### Files to add
- `backend/tests/test_scheduler_queue_empty.py` -- new test file for this feature (keep existing `test_scheduler.py` untouched)

### Out of scope
- The actual "continue" task-generation logic (calling the LLM to analyze the issue and produce new tasks). This issue only needs to call `engine.send_message` (or a new `engine.generate_tasks` method) with a prompt asking the agent to create new tasks. The real AI planning behavior is a follow-up.
- UI changes (frontend will read the config field from the existing `SessionRead` schema via the `config` dict).

## Behavior options

The session config dict gains a new key `queue_empty_action` with three allowed values:

| Value | Behavior | Session status after |
|-------|----------|---------------------|
| `stop` | Session goes idle. No further action. This is the **default** and matches current behavior. | `idle` |
| `continue` | Scheduler calls the engine to generate new tasks from the session's linked issue, then picks up the first new task. If no issue is linked, falls back to `stop`. | `executing` (or `idle` if generation produces no tasks) |
| `ask` | Scheduler creates a PendingQuestion: "All tasks are complete. Should I continue generating new tasks or stop?" Session transitions to `waiting_input`. | `waiting_input` |

### `continue` flow in detail
1. Scheduler detects queue is empty and `queue_empty_action == "continue"`.
2. Scheduler loads the session's linked issue (`session.issue_id`). If `None`, fall back to `stop` behavior.
3. Scheduler calls `engine.send_message(session_id, <prompt>)` where the prompt asks the agent to analyze the issue and create new tasks via the task queue. The prompt should include the issue title and description.
4. After the engine call returns, scheduler calls `get_next_task`. If a new task exists, it starts it. If not, session goes `idle`.
5. Emit `queue_empty.continue` event before calling the engine.

### `ask` flow in detail
1. Scheduler detects queue is empty and `queue_empty_action == "ask"`.
2. Scheduler calls `create_question(db, session_id, "All tasks are complete. Should I continue generating new tasks or stop?")`.
3. Session transitions to `waiting_input`.
4. Emit `queue_empty.ask` event.
5. When the user answers (via existing `on_question_answered` path), no special handling needed -- the session will go `idle` as it does today, and the user can manually add tasks or trigger a new run.

## Dependencies
- Depends on: #10 (scheduler) -- DONE
- Depends on: #09 (engine adapter) -- DONE
- Depends on: #05 (session CRUD) -- DONE
- Depends on: #46 (issue tracker API) -- DONE (needed for `continue` to load issue details)

## Acceptance Criteria

- [ ] `QueueEmptyAction` enum with values `stop`, `continue`, `ask` exists in `backend/codehive/api/schemas/session.py`
- [ ] Session creation and update reject invalid `queue_empty_action` values in the config dict (returns 422 or raises `ValueError`)
- [ ] When `queue_empty_action` is absent or `stop`: scheduler sets session to `idle` (existing behavior preserved, no regression)
- [ ] When `queue_empty_action == "ask"`: scheduler creates a PendingQuestion with a clear message and sets session to `waiting_input`
- [ ] When `queue_empty_action == "continue"` and session has a linked issue: scheduler calls `engine.send_message` with a prompt containing the issue title/description, then attempts to pick up the next task
- [ ] When `queue_empty_action == "continue"` and session has NO linked issue: falls back to `stop` behavior (session goes `idle`)
- [ ] Events `queue_empty.continue` and `queue_empty.ask` are emitted at the appropriate points
- [ ] All existing scheduler tests in `test_scheduler.py` continue to pass (no regressions)
- [ ] `uv run pytest backend/tests/test_scheduler_queue_empty.py -v` passes with 8+ new tests
- [ ] `uv run pytest backend/tests/ -v` passes with zero failures

## Test Scenarios

### Unit: `stop` behavior (default / backward compatibility)
- Queue empties with no `queue_empty_action` in config -- session goes `idle` (same as before)
- Queue empties with `queue_empty_action == "stop"` -- session goes `idle`
- Verify `session.status_changed` event emitted with status `idle`

### Unit: `ask` behavior
- Queue empties with `queue_empty_action == "ask"` -- a PendingQuestion is created with expected text
- Session transitions to `waiting_input`
- `queue_empty.ask` event is emitted
- Engine `start_task` is NOT called

### Unit: `continue` behavior
- Queue empties with `queue_empty_action == "continue"` and session has `issue_id` -- `engine.send_message` is called with a prompt containing the issue title
- `queue_empty.continue` event is emitted before the engine call
- If engine produces new tasks, scheduler picks up the next one (mock `get_next_task` to return a task after the engine call)
- If engine produces no new tasks, session goes `idle`

### Unit: `continue` fallback when no issue linked
- Queue empties with `queue_empty_action == "continue"` and `session.issue_id is None` -- session goes `idle` (fallback to `stop`)
- No engine call is made

### Unit: Validation
- Creating a session with `config={"queue_empty_action": "invalid"}` raises an error or returns 422
- Creating a session with `config={"queue_empty_action": "ask"}` succeeds

### Unit: Event emission
- Verify `queue_empty.ask` event data includes `question_id`
- Verify `queue_empty.continue` event data includes `issue_id`

## Log

### [SWE] 2026-03-16 12:00
- Implemented configurable `queue_empty_action` with three options: `stop` (default), `continue`, `ask`
- Added `QueueEmptyAction` enum and `_validate_queue_empty_action` helper to `api/schemas/session.py`
- Added config validation to `SessionCreate` and `SessionUpdate` via `field_validator`
- Added config validation to `core/session.py` in `create_session` and `update_session`
- Refactored scheduler `on_task_completed` else branch into `_handle_queue_empty` dispatch method
- Added `_transition_to_idle` helper to reduce duplication
- Extended `EngineAdapter` protocol in scheduler to include `send_message`
- Files modified:
  - `backend/codehive/core/scheduler.py`
  - `backend/codehive/api/schemas/session.py`
  - `backend/codehive/core/session.py`
- Files added:
  - `backend/tests/test_scheduler_queue_empty.py`
- Tests added: 18 new tests covering all behaviors (stop, ask, continue, fallback, validation, enum)
- Build results: 1200 tests pass (all), 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-16 12:30
- Tests: 1200 passed, 0 failed (18 new in test_scheduler_queue_empty.py, 14 existing in test_scheduler.py)
- Ruff check: clean
- Ruff format: clean
- Acceptance criteria:
  1. QueueEmptyAction enum with stop/continue/ask in schemas/session.py: PASS
  2. Session create/update reject invalid queue_empty_action (ValueError at schema and service layer): PASS
  3. queue_empty_action absent or stop -- scheduler sets session to idle (backward compat): PASS
  4. queue_empty_action == ask -- creates PendingQuestion, sets waiting_input: PASS
  5. queue_empty_action == continue with linked issue -- calls engine.send_message with issue title/description, picks up next task: PASS
  6. queue_empty_action == continue with no linked issue -- falls back to stop (idle): PASS
  7. Events queue_empty.continue (with issue_id) and queue_empty.ask (with question_id) emitted: PASS
  8. All existing scheduler tests pass (no regressions): PASS
  9. test_scheduler_queue_empty.py passes with 18 tests (>= 8 required): PASS
  10. Full test suite passes with zero failures: PASS
- VERDICT: PASS

### [PM] 2026-03-16 13:15
- Reviewed diff: 3 files modified, 1 file added (168 lines of production code, 574 lines of tests)
- Results verified: 18/18 new tests pass, 14/14 existing scheduler tests pass, no regressions
- Code quality: clean dispatch pattern in `_handle_queue_empty`, proper `_transition_to_idle` helper, `EngineAdapter` protocol correctly extended with `send_message`, validation at both schema and service layers
- Acceptance criteria: all 10/10 met
  1. QueueEmptyAction enum (stop/continue/ask) in schemas/session.py: MET
  2. Session create/update reject invalid values (ValueError): MET
  3. Absent or stop -> idle (backward compat): MET
  4. ask -> PendingQuestion + waiting_input: MET
  5. continue + linked issue -> engine.send_message with issue title/description, picks up next task: MET
  6. continue + no issue -> fallback to stop (idle): MET
  7. Events queue_empty.continue (with issue_id) and queue_empty.ask (with question_id): MET
  8. Existing scheduler tests pass (14/14): MET
  9. New test file passes with 18 tests (>= 8 required): MET
  10. Full suite zero failures: MET
- Follow-up issues created: none needed
- VERDICT: ACCEPT
