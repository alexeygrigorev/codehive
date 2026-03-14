# 46: Issue Tracker API

## Description
Implement the project-level issue tracker API. Issues are long-lived project tasks (like GitHub Issues) that can have multiple sessions working on them. Support CRUD operations and linking sessions to issues.

## Scope
- `backend/codehive/api/routes/issues.py` -- Issue CRUD endpoints
- `backend/codehive/core/issues.py` -- Issue business logic (create, update status, link sessions)
- `backend/tests/test_issues.py` -- Issue API tests

## Endpoints
- `POST /api/projects/{project_id}/issues` -- Create issue
- `GET /api/projects/{project_id}/issues` -- List issues for project (with status filter)
- `GET /api/issues/{id}` -- Get issue with linked sessions
- `PATCH /api/issues/{id}` -- Update issue (title, description, status)
- `DELETE /api/issues/{id}` -- Delete issue
- `POST /api/issues/{id}/link-session/{session_id}` -- Link a session to an issue

## Dependencies
- Depends on: #03 (Issue DB model)
- Depends on: #04 (project CRUD, since issues belong to projects)
