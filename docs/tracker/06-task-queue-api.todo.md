# 06: Task Queue API

## Description
REST API endpoints for managing the ToDo/task queue within a session.

## Scope
- `backend/codehive/api/routes/tasks.py` — Task CRUD endpoints
- `backend/codehive/core/task_queue.py` — Task queue logic (ordering, dependencies, auto-next)
- `backend/tests/test_tasks.py` — API tests

## Endpoints
- `POST /api/sessions/{session_id}/tasks` — create task
- `GET /api/sessions/{session_id}/tasks` — list tasks for session
- `PATCH /api/tasks/{id}` — update task (status, priority)
- `DELETE /api/tasks/{id}` — delete task
- `POST /api/sessions/{session_id}/tasks/reorder` — reorder tasks

## Task statuses
pending, running, blocked, done, failed, skipped

## Dependencies
- Depends on: #05 (needs session endpoints)
