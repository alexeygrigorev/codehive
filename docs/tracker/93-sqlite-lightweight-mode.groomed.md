# Issue #93: Lightweight SQLite mode -- no PostgreSQL or Redis required

**STATUS: Split into sub-issues. Do not implement this issue directly.**

## Split

This issue was too large for a single implementation pass. It has been split into three sub-issues with explicit dependencies:

1. **#93a - SQLite-compatible models** (`93a-sqlite-compatible-models.groomed.md`)
   - Replace PostgreSQL-specific types (JSONB, UUID) with portable types
   - Remove the duplicated `_sqlite_compatible_metadata()` from all 38 test files
   - Move `aiosqlite` from dev to runtime dependency
   - Dependencies: none

2. **#93b - In-memory LocalEventBus** (`93b-local-event-bus.groomed.md`)
   - Create `LocalEventBus` using asyncio primitives (replaces Redis when not configured)
   - Update WebSocket handler to work without Redis
   - Factory function to auto-select bus type
   - Dependencies: none (parallel with #93a)

3. **#93c - SQLite default config** (`93c-sqlite-default-config.groomed.md`)
   - Change default `database_url` to SQLite, default `redis_url` to empty
   - Configure SQLite engine (WAL mode, check_same_thread)
   - Update Alembic to work with both dialects
   - `codehive serve` works with zero infrastructure
   - Dependencies: #93a, #93b

## Implementation Order

```
#93a (models) ----\
                   +--> #93c (config + startup)
#93b (event bus) -/
```

#93a and #93b can be implemented in parallel. #93c depends on both.

## Original Problem

Currently Codehive requires PostgreSQL + Redis just to start. For a single-user self-hosted tool, this is heavy. Many users just want to `uv run codehive serve` and go.

## Original Requirements

- [x] Support SQLite as the database backend (via `aiosqlite` + SQLAlchemy async) -- #93a
- [x] SQLite should be the default -- #93c
- [x] Replace Redis pub/sub with an in-process alternative when Redis is not configured -- #93b
- [x] Replace Redis-based event bus with a `LocalEventBus` -- #93b
- [x] `codehive serve` should work with zero infrastructure -- #93c
- [x] PostgreSQL + Redis remain supported for production -- #93c
- [x] Auto-detect: if `DATABASE_URL` starts with `sqlite`, use SQLite mode; if `REDIS_URL` is empty, use local event bus -- #93b, #93c
- [x] Alembic migrations should work with both SQLite and PostgreSQL -- #93a, #93c
