# 03: Database Models

## Description
Define SQLAlchemy models for all core entities and set up Alembic migrations.

## Scope
- `backend/codehive/db/models.py` — SQLAlchemy models: Workspace, Project, Issue, Session, Task, Message, Event, Checkpoint, PendingQuestion
- `backend/codehive/db/session.py` — Async DB session factory (asyncpg)
- `backend/alembic.ini` + `backend/codehive/db/migrations/` — Alembic setup
- `backend/tests/test_models.py` — Model creation tests

## Key fields per model
- **Workspace**: id, name, root_path, settings (JSONB), created_at
- **Project**: id, workspace_id (FK), name, path, description, archetype, knowledge (JSONB), created_at
- **Issue**: id, project_id (FK), title, description, status, github_issue_id, created_at
- **Session**: id, project_id (FK), issue_id (FK nullable), parent_session_id (FK nullable, self-ref), name, engine, mode, status, config (JSONB), created_at
- **Task**: id, session_id (FK), title, instructions, status, priority, depends_on, mode (auto/manual), created_by, created_at
- **Message**: id, session_id (FK), role (user/assistant/system/tool), content, metadata (JSONB), created_at
- **Event**: id, session_id (FK), type, data (JSONB), created_at
- **Checkpoint**: id, session_id (FK), git_ref, state (JSONB), created_at
- **PendingQuestion**: id, session_id (FK), question, context, answered, answer, created_at

## Dependencies
- Depends on: #02 (needs Postgres running)
