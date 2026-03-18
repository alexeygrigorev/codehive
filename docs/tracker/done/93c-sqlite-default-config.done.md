# Issue #93c: SQLite as default database, zero-infrastructure startup

Parent: #93 (Lightweight SQLite mode)

## Problem

The default `database_url` in `config.py` points to PostgreSQL (`postgresql+asyncpg://...`). The default `redis_url` points to Redis (`redis://localhost:6379/0`). This means `uv run codehive serve` fails immediately without Docker running. For a single-user self-hosted tool, the default should be zero infrastructure.

## Scope

Change defaults so that `codehive serve` works out of the box with SQLite and no Redis. Ensure Alembic migrations work with SQLite. Ensure the DB engine is configured correctly for SQLite (WAL mode, etc.).

## Requirements

- [ ] Default `database_url` in `Settings` changes to `sqlite+aiosqlite:///codehive.db`
- [ ] Default `redis_url` in `Settings` changes to `""` (empty string = no Redis)
- [ ] `session.py` (`create_async_engine_from_settings`) detects SQLite URLs and applies SQLite-appropriate engine kwargs (e.g., `connect_args={"check_same_thread": False}`)
- [ ] When using SQLite, enable WAL mode on connection (via SQLAlchemy event listener)
- [ ] Alembic `env.py` reads the database URL from `Settings` (not hardcoded in `alembic.ini`), supporting both PostgreSQL and SQLite
- [ ] `alembic.ini` default URL updated to match the new SQLite default
- [ ] `codehive serve` starts successfully with no environment variables set (pure defaults)
- [ ] PostgreSQL + Redis remain fully supported by setting `CODEHIVE_DATABASE_URL` and `CODEHIVE_REDIS_URL`
- [ ] Existing Alembic migrations work with SQLite (if not, create a new baseline migration that is dialect-aware)

## Design

### session.py changes
```python
def create_async_engine_from_settings(database_url=None, **engine_kwargs):
    url = database_url or Settings().database_url
    if url.startswith("sqlite"):
        engine_kwargs.setdefault("connect_args", {"check_same_thread": False})
    engine = create_async_engine(url, **engine_kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
    return engine
```

### Alembic env.py changes
```python
from codehive.config import Settings
# Override sqlalchemy.url from Settings if available
settings = Settings()
config.set_main_option("sqlalchemy.url", settings.database_url)
```

## Dependencies

- #93a (SQLite-compatible models must land first so tables can be created on SQLite)
- #93b (LocalEventBus must exist so the server can start without Redis)

## Acceptance Criteria

- [ ] `uv run codehive serve` starts with zero environment variables, zero Docker, zero infrastructure
- [ ] The server creates `codehive.db` in the current directory on first run
- [ ] API endpoints work (e.g., `GET /api/health` returns 200)
- [ ] `uv run alembic upgrade head` works with the default SQLite URL
- [ ] Setting `CODEHIVE_DATABASE_URL=postgresql+asyncpg://...` switches to PostgreSQL
- [ ] Setting `CODEHIVE_REDIS_URL=redis://...` switches to Redis event bus
- [ ] `uv run pytest tests/ -v` passes (no regressions)
- [ ] `uv run ruff check` passes clean

## Test Scenarios

### Unit: Config defaults
- Default `Settings().database_url` starts with `sqlite`
- Default `Settings().redis_url` is empty string
- Override via env var: `CODEHIVE_DATABASE_URL=postgresql+asyncpg://...` is respected

### Unit: Engine creation
- `create_async_engine_from_settings()` with SQLite URL sets `check_same_thread=False`
- SQLite engine has WAL mode enabled on connection

### Integration: Server startup
- Start FastAPI app with default config, verify `/api/health` returns 200
- Verify SQLite database file is created

### Integration: Alembic
- Run `alembic upgrade head` against SQLite, verify tables are created

## Log

### [SWE] 2026-03-18 12:00
- Reviewed previous SWE's work -- all implementation was already complete
- Verified all code changes match the issue requirements:
  - config.py: database_url defaults to sqlite+aiosqlite:///codehive.db, redis_url defaults to ""
  - session.py: create_async_engine_from_settings detects SQLite, sets check_same_thread=False, enables WAL mode via event listener
  - alembic.ini: sqlalchemy.url updated to sqlite+aiosqlite:///codehive.db
  - env.py: reads URL from Settings, handles SQLite connect_args for async migrations
  - test_config.py: tests for SQLite default and empty redis_url already present
  - test_sqlite_config.py: comprehensive tests for config defaults, engine creation, WAL mode, and table creation on SQLite
- Files already modified by previous SWE: backend/codehive/config.py, backend/codehive/db/session.py, backend/alembic.ini, backend/codehive/db/migrations/env.py, backend/tests/test_config.py, backend/tests/test_sqlite_config.py
- Tests added: 9 tests in test_sqlite_config.py (config defaults, engine creation, WAL mode memory + file, table creation), 4 tests in test_config.py (database/redis URL defaults and overrides)
- Build results: 1739 tests pass, 12 fail (pre-existing WebSocket test failures unrelated to this issue -- they fail because app lifespan tries to access tables not created in those test fixtures), 3 skipped, ruff clean, format clean
- Known limitations: 12 pre-existing test failures in test_events.py and test_ws_auth.py are unrelated to this issue (WebSocket integration tests that fail due to missing table setup in their fixtures)
