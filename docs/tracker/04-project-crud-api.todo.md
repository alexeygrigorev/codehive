# 04: Project CRUD API

## Description
REST API endpoints for creating, listing, reading, updating, and deleting projects.

## Scope
- `backend/codehive/api/routes/projects.py` — CRUD endpoints
- `backend/codehive/core/project.py` — Project business logic
- `backend/tests/test_projects.py` — API tests

## Endpoints
- `POST /api/projects` — create project
- `GET /api/projects` — list projects
- `GET /api/projects/{id}` — get project
- `PATCH /api/projects/{id}` — update project
- `DELETE /api/projects/{id}` — delete project

## Dependencies
- Depends on: #03 (needs DB models)
