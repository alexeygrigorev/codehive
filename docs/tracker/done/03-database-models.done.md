# 03: Database Models

## Description
Define SQLAlchemy async models for all core entities, set up the async DB session factory (asyncpg), and configure Alembic for migrations.

## Scope
- `backend/codehive/db/__init__.py` — package init
- `backend/codehive/db/models.py` — SQLAlchemy models: Workspace, Project, Issue, Session, Task, Message, Event, Checkpoint, PendingQuestion
- `backend/codehive/db/session.py` — Async DB session factory using `async_sessionmaker` with asyncpg
- `backend/alembic.ini` + `backend/codehive/db/migrations/` — Alembic setup with async support
- `backend/tests/test_models.py` — Model creation and relationship tests

## Key fields per model
- **Workspace**: id (UUID PK), name (unique, non-null), root_path (non-null), settings (JSONB, default {}), created_at (server default now)
- **Project**: id (UUID PK), workspace_id (FK -> workspaces.id, non-null), name (non-null), path, description, archetype, knowledge (JSONB, default {}), created_at
- **Issue**: id (UUID PK), project_id (FK -> projects.id, non-null), title (non-null), description, status (varchar, default "open"), github_issue_id (nullable int), created_at
- **Session**: id (UUID PK), project_id (FK -> projects.id, non-null), issue_id (FK -> issues.id, nullable), parent_session_id (FK -> sessions.id, nullable, self-ref), name (non-null), engine (varchar, non-null), mode (varchar, non-null), status (varchar, default "idle"), config (JSONB, default {}), created_at
- **Task**: id (UUID PK), session_id (FK -> sessions.id, non-null), title (non-null), instructions (text), status (varchar, default "pending"), priority (int, default 0), depends_on (UUID, nullable), mode (varchar, default "auto"), created_by (varchar, default "user"), created_at
- **Message**: id (UUID PK), session_id (FK -> sessions.id, non-null), role (varchar, non-null), content (text, non-null), metadata_ (JSONB, default {}), created_at
- **Event**: id (UUID PK), session_id (FK -> sessions.id, non-null), type (varchar, non-null), data (JSONB, default {}), created_at
- **Checkpoint**: id (UUID PK), session_id (FK -> sessions.id, non-null), git_ref (varchar, non-null), state (JSONB, default {}), created_at
- **PendingQuestion**: id (UUID PK), session_id (FK -> sessions.id, non-null), question (text, non-null), context (text, nullable), answered (boolean, default false), answer (text, nullable), created_at

## Dependencies
- Depends on: #01 (FastAPI app setup) -- `.done.md`
- Depends on: #02 (Docker Compose with Postgres) -- `.done.md`

## New dependencies to add to pyproject.toml
- `sqlalchemy[asyncio]>=2.0`
- `asyncpg`
- `alembic`

## Acceptance Criteria

- [ ] `uv run pytest tests/test_models.py -v` passes with 9+ tests (one per model minimum)
- [ ] All 9 models exist in `backend/codehive/db/models.py`: Workspace, Project, Issue, Session, Task, Message, Event, Checkpoint, PendingQuestion
- [ ] All models use UUID primary keys (not auto-increment integers)
- [ ] All JSONB columns have a server-side default of `{}`
- [ ] All `created_at` columns have a server-side default of `now()`
- [ ] Foreign key relationships are correct: Project -> Workspace, Issue -> Project, Session -> Project, Session -> Issue (nullable), Session -> Session (self-ref, nullable), Task -> Session, Message -> Session, Event -> Session, Checkpoint -> Session, PendingQuestion -> Session
- [ ] `backend/codehive/db/session.py` exports an `async_sessionmaker` (or factory function) that creates async sessions using the `database_url` from `Settings`
- [ ] `backend/alembic.ini` exists and points to `codehive/db/migrations/`
- [ ] `backend/codehive/db/migrations/env.py` is configured for async (uses `run_async_migrations`) and imports all models via `target_metadata`
- [ ] `uv run alembic revision --autogenerate -m "initial"` succeeds and generates a migration with all 9 tables (run against running Postgres from docker-compose)
- [ ] `uv run alembic upgrade head` applies the migration successfully against the Postgres instance
- [ ] Session model `status` column accepts the spec values: idle, planning, executing, waiting_input, waiting_approval, blocked, completed, failed
- [ ] Task model `status` column accepts the spec values: pending, running, blocked, done, failed, skipped
- [ ] Issue model `status` column accepts the spec values: open, in_progress, closed
- [ ] `sqlalchemy[asyncio]`, `asyncpg`, and `alembic` are added to `pyproject.toml` dependencies

## Test Scenarios

### Unit: Model instantiation and field defaults
- Create each of the 9 models in-memory, verify all required fields are present and defaults are set (JSONB defaults to `{}`, booleans default correctly, status defaults are correct)
- Verify UUID PKs are generated (not None after flush)
- Verify `created_at` is populated after insert

### Unit: Foreign key relationships
- Create a Workspace, then a Project referencing it -- verify `project.workspace_id` is set
- Create a Project, then an Issue referencing it -- verify relationship
- Create a Session with `parent_session_id` pointing to another Session -- verify self-referential FK
- Create a Session with `issue_id = None` -- verify nullable FK is accepted
- Create a Task, Message, Event, Checkpoint, PendingQuestion referencing a Session -- verify FKs

### Integration: Alembic migrations
- Run `alembic upgrade head` against a clean Postgres database -- verify all 9 tables are created
- Run `alembic downgrade base` -- verify all tables are dropped
- Run `alembic current` -- verify it reports the correct head revision

### Integration: Async session factory
- Use the session factory to create a session, insert a Workspace, commit, and query it back -- verify round-trip works
- Verify the session factory reads `database_url` from Settings (or accepts a URL override for testing)

### Integration: Full entity graph
- Create a full chain: Workspace -> Project -> Issue -> Session -> (Task, Message, Event, Checkpoint, PendingQuestion) -- insert all, commit, and verify all entities persist with correct FK references

## Implementation Notes
- Use SQLAlchemy 2.0 `DeclarativeBase` (mapped_column style), not the legacy `declarative_base()`
- Table names should be lowercase plural: `workspaces`, `projects`, `issues`, `sessions`, `tasks`, `messages`, `events`, `checkpoints`, `pending_questions`
- Use `sqlalchemy.dialects.postgresql.UUID` and `JSONB` types for Postgres-specific columns
- The `metadata` column on Message should be named `metadata_` in Python (to avoid shadowing SQLAlchemy's `metadata`) but map to `metadata` in the database column name
- For tests that need a real database, use the Postgres instance from docker-compose (`CODEHIVE_DATABASE_URL` env var) or provide a fixture that creates/drops a test database

## Log

### [SWE] 2026-03-14 12:00
- Implemented all 9 SQLAlchemy 2.0 models (DeclarativeBase, mapped_column style) with UUID PKs, JSONB server defaults, created_at server defaults, and all FK relationships per spec
- Created async session factory in session.py with configurable database_url (reads from Settings by default)
- Configured Alembic for async (asyncpg) with run_async_migrations in env.py, target_metadata from Base
- Generated and applied initial migration (all 9 tables: workspaces, projects, issues, sessions, tasks, messages, events, checkpoints, pending_questions)
- Message model uses metadata_ in Python mapped to "metadata" column in DB
- Session self-referential FK (parent_session_id) with child_sessions relationship
- Added sqlalchemy[asyncio], asyncpg, alembic to pyproject.toml
- Files created: backend/codehive/db/__init__.py, backend/codehive/db/models.py, backend/codehive/db/session.py, backend/codehive/db/migrations/env.py, backend/alembic.ini, backend/codehive/db/migrations/versions/5ee984c421f1_initial.py, backend/tests/test_models.py
- Files modified: backend/pyproject.toml, backend/uv.lock
- Tests added: 19 tests in test_models.py (14 unit + 5 integration) covering model instantiation, defaults, status values, metadata registration, session factory, full entity graph round-trip, alembic upgrade/downgrade/current
- Build results: 48 tests pass (all), 0 fail, ruff clean
- Integration tests require running Postgres (auto-skipped via @pytest.mark.skipif if unavailable)
- Known limitations: none

### [QA] 2026-03-14 13:30
- Tests: 48 passed, 0 failed (19 in test_models.py, all integration tests ran with Postgres)
- Ruff check: clean
- Ruff format: clean (16 files already formatted)
- Acceptance criteria:
  - uv run pytest tests/test_models.py passes with 9+ tests (19 tests): PASS
  - All 9 models exist in models.py: PASS
  - All models use UUID primary keys: PASS
  - All JSONB columns have server_default '{}': PASS
  - All created_at columns have server_default now(): PASS
  - FK relationships correct (all 10 relationships verified): PASS
  - session.py exports async_sessionmaker factory reading from Settings: PASS
  - alembic.ini exists and points to codehive/db/migrations/: PASS
  - env.py configured for async with run_async_migrations and target_metadata: PASS
  - Initial migration generated with all 9 tables: PASS
  - alembic upgrade head succeeds against Postgres: PASS
  - Session status accepts all 8 spec values: PASS
  - Task status accepts all 6 spec values: PASS
  - Issue status accepts open, in_progress, closed: PASS
  - sqlalchemy[asyncio], asyncpg, alembic in pyproject.toml: PASS
- Note: 1 deprecation warning in test_models.py:35 (asyncio.get_event_loop() deprecated) -- non-blocking
- VERDICT: PASS

### [PM] 2026-03-14 14:00
- Reviewed diff: 7 new files (models.py, session.py, __init__.py, alembic.ini, env.py, initial migration, test_models.py) + 2 modified (pyproject.toml, uv.lock)
- Results verified: real data present -- QA ran 48 tests (19 model-specific), integration tests executed against live Postgres (upgrade/downgrade/current, full entity graph round-trip, session factory round-trip)
- Acceptance criteria: all 15 met
  - 9 models with UUID PKs, JSONB server defaults, created_at server defaults: verified in source
  - All FK relationships correct including Session self-ref and nullable Issue FK: verified in source and migration
  - Async session factory reads from Settings, accepts URL override: verified in source
  - Alembic configured for async with run_async_migrations and target_metadata: verified in env.py
  - Initial migration creates all 9 tables with correct columns and constraints: verified in migration file
  - Status columns accept all spec values (Session 8, Task 6, Issue 3): verified via unit tests
  - Dependencies added to pyproject.toml: verified (sqlalchemy[asyncio], asyncpg, alembic)
  - Message metadata_ mapped to "metadata" DB column: verified in models.py line 128-130
- Code quality: clean, follows SQLAlchemy 2.0 DeclarativeBase/mapped_column patterns, proper test cleanup, integration tests guarded with skipif
- Minor note: asyncio.get_event_loop() deprecation warning in test helper -- non-blocking, can be addressed in a future cleanup pass
- Follow-up issues created: none
- VERDICT: ACCEPT
