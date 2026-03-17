# Issue #93: Lightweight SQLite mode — no PostgreSQL or Redis required

## Problem

Currently Codehive requires PostgreSQL + Redis just to start. For a single-user self-hosted tool, this is heavy — you need Docker or system packages for two separate services. Many users just want to `pip install codehive && codehive serve` and go.

## Requirements

- [ ] Support SQLite as the database backend (via `aiosqlite` + SQLAlchemy async)
- [ ] SQLite should be the default — `CODEHIVE_DATABASE_URL=sqlite+aiosqlite:///codehive.db`
- [ ] Replace Redis pub/sub with an in-process alternative when Redis is not configured
  - Options: `asyncio.Queue`, `broadcast` library, or SQLite-backed queue
  - Pub/sub for WebSocket events can use in-memory channels (single process)
  - Event persistence can go to SQLite
- [ ] Replace Redis-based event bus with a `LocalEventBus` that uses asyncio primitives
- [ ] `codehive serve` should work with zero infrastructure — just Python
- [ ] PostgreSQL + Redis remain supported for production/multi-process deployments
- [ ] Auto-detect: if `DATABASE_URL` starts with `sqlite`, use SQLite mode; if `REDIS_URL` is empty, use local event bus
- [ ] Alembic migrations should work with both SQLite and PostgreSQL

## Notes

- SQLite with WAL mode handles concurrent reads well for single-user
- The `_NoOpEventBus` from `code_app.py` is a starting point for the local event bus — but it needs actual pub/sub for WebSocket streaming, not just discarding events
- This makes `codehive code` and `codehive serve` work out of the box with `uv run codehive serve` — no Docker needed
- Keep PostgreSQL + Redis as the recommended setup for anything beyond single-user local use
