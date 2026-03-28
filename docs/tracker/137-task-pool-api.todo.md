# 137 — Task pool API: create, list, and manage tasks programmatically

## Problem
Currently tasks are tracked as markdown files in docs/tracker/. The orchestrator and agents need to communicate through a proper API — creating tasks, claiming them, updating status, and reading each other's logs.

## Vision
A REST API for the task pool that agents use to coordinate:
- `POST /api/tasks` — add a task to the backlog
- `GET /api/tasks` — list tasks, filterable by status/project
- `PATCH /api/tasks/{id}` — update status, add log entries
- `GET /api/tasks/{id}` — get task details including full log

The task pool replaces the file-based tracker. Agents read/write tasks through the API instead of editing markdown files.

## What this looks like
- Task has: title, description, acceptance_criteria, status, assigned_agent, project_id, logs[]
- Log entries: timestamp, agent_role, content (what the agent did/found)
- Agents append log entries as they work — this is how they communicate
- The orchestrator queries for tasks ready for the next pipeline step

## Acceptance criteria
- [ ] CRUD API for tasks with all fields
- [ ] Log entries API (append-only)
- [ ] Filter by status, project, assigned agent
- [ ] Proper validation (required fields, valid status transitions)
- [ ] Database model with migrations
