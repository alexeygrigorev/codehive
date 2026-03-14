# 47: Workspace Management API

## Description
Implement the workspace management API. The workspace is the root-level container that holds all projects, global settings, integrations, secrets config, and the agent role library.

## Scope
- `backend/codehive/api/routes/workspace.py` -- Workspace CRUD endpoints
- `backend/codehive/core/workspace.py` -- Workspace business logic (create, update settings, manage global config)
- `backend/tests/test_workspace.py` -- Workspace API tests

## Endpoints
- `POST /api/workspaces` -- Create workspace
- `GET /api/workspaces` -- List workspaces
- `GET /api/workspaces/{id}` -- Get workspace with settings
- `PATCH /api/workspaces/{id}` -- Update workspace settings
- `GET /api/workspaces/{id}/projects` -- List projects in workspace

## Dependencies
- Depends on: #03 (Workspace DB model)
