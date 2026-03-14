# 48: Project Knowledge Base and Agent Charter

## Description
Implement the project knowledge base -- a structured store for tech stack info, architecture decisions, coding conventions, and the agent charter (goals, constraints, decision policies). The agent consults this when making autonomous decisions.

## Scope
- `backend/codehive/core/knowledge.py` -- Knowledge base CRUD: read/write knowledge entries, manage agent charter document
- `backend/codehive/api/routes/knowledge.py` -- Endpoints for managing project knowledge and agent charter
- `backend/codehive/engine/native.py` -- Extend to inject relevant knowledge into agent context
- `backend/tests/test_knowledge.py` -- Knowledge base tests

## Endpoints
- `GET /api/projects/{project_id}/knowledge` -- Get project knowledge (JSONB)
- `PATCH /api/projects/{project_id}/knowledge` -- Update project knowledge
- `GET /api/projects/{project_id}/charter` -- Get agent charter
- `PUT /api/projects/{project_id}/charter` -- Set/update agent charter

## Dependencies
- Depends on: #03 (Project model with knowledge JSONB field)
- Depends on: #04 (project CRUD API)
