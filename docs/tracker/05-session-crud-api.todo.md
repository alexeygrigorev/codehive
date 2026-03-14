# 05: Session CRUD API

## Description
REST API endpoints for creating, listing, reading, and managing sessions within a project.

## Scope
- `backend/codehive/api/routes/sessions.py` — CRUD + status endpoints
- `backend/codehive/core/session.py` — Session lifecycle logic and state machine
- `backend/tests/test_sessions.py` — API tests

## Endpoints
- `POST /api/projects/{project_id}/sessions` — create session (with engine, mode)
- `GET /api/projects/{project_id}/sessions` — list sessions for project
- `GET /api/sessions/{id}` — get session with status
- `PATCH /api/sessions/{id}` — update session (mode, config)
- `POST /api/sessions/{id}/pause` — pause session
- `POST /api/sessions/{id}/resume` — resume session

## Session statuses
idle, planning, executing, waiting_input, waiting_approval, blocked, completed, failed

## Dependencies
- Depends on: #04 (needs project endpoints to create a project first)
