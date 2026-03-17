# Issue #93a: SQLite-compatible SQLAlchemy models

Parent: #93 (Lightweight SQLite mode)

## Problem

All SQLAlchemy models use PostgreSQL-specific types (`JSONB`, `UUID(as_uuid=True)`) and PostgreSQL-specific server defaults (`text("now()")`, `text("'{}'::jsonb")`). This prevents using SQLite as a database backend. Every test file (38 files) duplicates a `_sqlite_compatible_metadata()` function to work around this at test time.

## Scope

Make the models work natively with both PostgreSQL and SQLite, eliminating the need for the test-time metadata hack.

## Requirements

- [ ] Replace `JSONB` with a portable type that renders as `JSONB` on PostgreSQL and `JSON` on SQLite
- [ ] Replace `UUID(as_uuid=True)` with a portable type that renders as `UUID` on PostgreSQL and `CHAR(32)`/`String(36)` on SQLite (or use `TypeDecorator`)
- [ ] Replace `server_default=text("now()")` with a portable default (e.g., `server_default=text("CURRENT_TIMESTAMP")` works on both)
- [ ] Replace `server_default=text("'{}'::jsonb")` with a portable default (e.g., `server_default=text("'{}'")`)
- [ ] Replace `server_default=text("true")` / `server_default=text("false")` with portable equivalents (`text("1")` / `text("0")` or use `server_default=text("TRUE")`)
- [ ] Remove the duplicated `_sqlite_compatible_metadata()` from all 38 test files -- tests should use `Base.metadata` directly
- [ ] All existing tests pass without the metadata hack
- [ ] `aiosqlite` moves from dev dependency to a runtime dependency in `pyproject.toml`

## Approach

Use SQLAlchemy `TypeDecorator` or `with_variant()` for types that differ between dialects:

```python
from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, UUID as PG_UUID

# Option A: with_variant
json_col = mapped_column(JSON().with_variant(PG_JSONB(), "postgresql"), ...)

# Option B: TypeDecorator (cleaner for UUID)
class PortableUUID(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value
        return value
```

## Dependencies

- None (this is foundational -- #93b and #93c depend on this)

## Acceptance Criteria

- [ ] `uv run pytest tests/ -v` passes with all existing tests (no regressions)
- [ ] `_sqlite_compatible_metadata()` is removed from all test files
- [ ] Test files use `Base.metadata` directly to create tables
- [ ] Models can create tables on both SQLite and PostgreSQL without errors
- [ ] `aiosqlite` is listed under `[project] dependencies` (not just dev)
- [ ] `uv run ruff check` passes clean

## Test Scenarios

### Unit: Model portability
- Create all tables via `Base.metadata.create_all()` on SQLite -- verify no errors
- Insert a row with a UUID primary key on SQLite -- verify it round-trips as `uuid.UUID`
- Insert a row with a JSONB field on SQLite -- verify JSON data round-trips correctly
- Verify `created_at` server defaults produce valid timestamps on SQLite

### Integration: Existing test suite
- All 38 existing test files pass without `_sqlite_compatible_metadata()` (they already use SQLite, so removing the hack and using Base.metadata directly is the test)

## Log

### [SWE] 2026-03-17 12:00
- Implemented portable SQLAlchemy types in `backend/codehive/db/models.py`:
  - `PortableUUID` TypeDecorator: UUID on PostgreSQL, CHAR(36) on SQLite, round-trips as `uuid.UUID`
  - `PortableJSON`: `JSON().with_variant(PG_JSONB(), "postgresql")` -- JSONB on PG, JSON on SQLite
  - Replaced all `server_default=text("now()")` with `text("CURRENT_TIMESTAMP")`
  - Replaced all `server_default=text("'{}'::jsonb")` with `text("'{}'")`
  - Replaced `server_default=text("true"/"false")` with `text("1"/"0")`
- Removed `_sqlite_compatible_metadata()` from all 40 test files (38 original + 2 new files that also had it)
- All test files now use `Base.metadata` directly for table creation/teardown
- Moved `aiosqlite` from dev dependency to runtime dependency in `pyproject.toml`
- Added 3 missing `Base` imports in test_archetypes.py, test_modes.py, test_roles.py
- Fixed 51 unused import warnings via `ruff --fix`
- Created `tests/test_portable_models.py` with 10 dedicated portability tests
- Files modified: `backend/codehive/db/models.py`, `backend/pyproject.toml`, 40 test files, 1 new test file
- Tests added: 10 portability tests (UUID round-trip, JSON round-trip, server defaults, full entity graph)
- Build results: 1742 tests pass (1732 existing + 10 new), 0 fail, 3 skipped, ruff clean
