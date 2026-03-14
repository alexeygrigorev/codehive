# 10: Session Scheduler (Auto-Next + Pending Questions)

## Description
Implement the session scheduler that auto-picks the next task from the ToDo queue and manages pending questions.

## Scope
- `backend/codehive/core/session.py` — Extend with scheduler logic
- `backend/codehive/core/task_queue.py` — Extend with auto-next behavior
- `backend/codehive/api/routes/questions.py` — Pending questions endpoints
- `backend/tests/test_scheduler.py` — Scheduler tests

## Behavior
- After a task completes: if queue is enabled and tasks remain, auto-start next task
- If agent asks a question and tasks remain: save question to pending_questions, continue with next task
- If agent asks a question and no tasks remain: session enters `waiting_input`
- Pending questions can be answered later via API; answers are injected into the session context

## Endpoints
- `GET /api/sessions/{id}/questions` — list pending questions
- `POST /api/questions/{id}/answer` — answer a question

## Dependencies
- Depends on: #06 (task queue), #09 (engine adapter)
