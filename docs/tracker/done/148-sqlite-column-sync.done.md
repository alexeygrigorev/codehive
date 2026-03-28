# 148 — SQLite auto-sync missing columns on startup

## Problem

After adding new columns to SQLAlchemy models (e.g., `Session.role`, `Session.task_id`, `Session.pipeline_step` from issues #136-#145), existing SQLite databases do not get updated. SQLAlchemy's `Base.metadata.create_all()` only creates new tables -- it never adds columns to existing tables.

This causes 500 errors at runtime when the app tries to SELECT or INSERT rows that reference columns missing from the physical schema. The user sees "Failed to fetch" after creating a project because the API serializes Session rows including columns that do not exist in the DB.

## Root Cause

`create_all` in `app.py` lifespan (line 66) only handles new tables. Existing tables with missing columns silently break at runtime when SQLAlchemy generates SQL referencing those columns.

## User Story

### Story: Returning user upgrades codehive and hits 500 errors

1. User has been running codehive for a while with an existing SQLite database containing projects and sessions
2. User upgrades codehive to a version that added new columns to the Session model (role, task_id, pipeline_step)
3. User starts the server with `uv run codehive serve`
4. User opens the dashboard and clicks on an existing project
5. The API returns a 500 error because `SELECT sessions.role ...` fails -- the `role` column does not exist in the physical SQLite table
6. User sees "Failed to fetch" in the browser

**Expected after fix:** Step 3 detects the missing columns and runs `ALTER TABLE sessions ADD COLUMN role ...` (and others) automatically. Step 4-5 work normally.

## Acceptance Criteria

- [ ] A `_sync_sqlite_columns()` helper function exists (in `backend/codehive/db/sync_columns.py` or similar)
- [ ] The function uses `inspect()` to compare model metadata columns against actual SQLite table columns
- [ ] For each missing column, it executes `ALTER TABLE <table> ADD COLUMN <col> <type>` with correct SQLite-compatible types
- [ ] Server defaults (e.g., `server_default=text("CURRENT_TIMESTAMP")`) are included in the ALTER statement when present
- [ ] Nullable columns that have no server_default get added as `NULL`-able (SQLite requires this for ALTER TABLE ADD COLUMN)
- [ ] Existing data is preserved -- no DROP TABLE, no recreate; purely additive ALTER TABLE ADD COLUMN
- [ ] The function is called during app lifespan startup, after `create_all`, only when the DB URL starts with `sqlite`
- [ ] Each added column is logged at INFO level (e.g., "Added column sessions.role (VARCHAR(50))")
- [ ] If no columns are missing, the function completes silently (no unnecessary logging)
- [ ] Bug fix verified with TDD: a test creates a DB without the new columns, confirms the failure mode, then runs the sync and confirms the fix
- [ ] All existing tests continue to pass: `cd backend && uv run pytest tests/ -v`
- [ ] Lint clean: `cd backend && uv run ruff check`

## Technical Notes

### Fix Approach

1. Create `backend/codehive/db/sync_columns.py` with a `sync_sqlite_columns(conn)` function that:
   - Calls `sqlalchemy.inspect(conn)` to get the `Inspector`
   - Iterates `Base.metadata.sorted_tables`
   - For each table, compares `inspector.get_columns(table.name)` against `table.columns`
   - For each missing column, builds and executes an `ALTER TABLE ADD COLUMN` DDL statement
   - Uses `column.type.compile(dialect=conn.dialect)` to get the correct SQLite type string
   - Appends `DEFAULT <value>` if `column.server_default` is set

2. In `app.py` lifespan, call it inside the existing `if settings.database_url.startswith("sqlite")` block, right after `create_all`:
   ```python
   from codehive.db.sync_columns import sync_sqlite_columns
   await conn.run_sync(sync_sqlite_columns)
   ```

3. The function receives a sync `Connection` (from `run_sync`) and operates synchronously.

### SQLite ALTER TABLE Constraints

- SQLite only supports `ALTER TABLE ADD COLUMN` -- no DROP, no RENAME, no type changes
- Added columns MUST be nullable OR have a DEFAULT value (SQLite constraint)
- All new columns in our models are either nullable or have server_default, so this is safe

### Column Type Mapping

Use `column.type.compile(dialect=connection.dialect)` to get the correct type. Our `PortableUUID` compiles to `VARCHAR(36)` on SQLite, `PortableJSON` compiles to `JSON`, etc.

## Test Scenarios

### Unit: _sync_sqlite_columns helper

1. **Missing columns are detected and added** -- Create a SQLite DB with `sessions` table missing `role`, `task_id`, `pipeline_step`. Run `sync_sqlite_columns`. Verify the columns now exist via `PRAGMA table_info(sessions)`.

2. **Existing columns are not touched** -- Create a complete DB (all columns present). Run `sync_sqlite_columns`. Verify no ALTER TABLE statements are executed (check log output or mock).

3. **Server defaults are applied** -- Create a table missing a column that has `server_default`. Run sync. Insert a row without specifying that column. Verify the default value is applied.

4. **Multiple tables handled** -- Create a DB missing columns on more than one table. Run sync. Verify all missing columns across all tables are added.

### Integration: TDD bug reproduction

5. **TDD red-green cycle** -- This is the key bug-fix test:
   - Create a SQLite DB with an old schema (sessions table without `role`, `task_id`, `pipeline_step`)
   - Insert a session row using raw SQL (simulating existing data)
   - Attempt to query sessions via SQLAlchemy ORM -- confirm it FAILS (OperationalError or similar)
   - Run `sync_sqlite_columns`
   - Retry the same ORM query -- confirm it SUCCEEDS
   - Verify the old session row still exists with its original data intact

### Integration: Lifespan integration

6. **Sync runs on startup** -- Use the FastAPI test client with a pre-built SQLite DB that has missing columns. Verify the app starts without error and the columns are present after startup.

## Dependencies

- None -- this is a standalone bug fix with no dependencies on other tracker issues.

## Log

### [SWE] 2026-03-28 10:00
- TDD red: wrote 7 tests in test_sqlite_column_sync.py, confirmed all 7 FAIL (ModuleNotFoundError)
- Implemented `sync_sqlite_columns()` in `backend/codehive/db/sync_columns.py`
  - Uses `sqlalchemy.inspect()` to compare model metadata columns vs physical DB columns
  - For each missing column, executes `ALTER TABLE ADD COLUMN` with correct SQLite type via `column.type.compile(dialect=dialect)`
  - Includes `DEFAULT <value>` when `column.server_default` is set
  - Logs each added column at INFO level
  - Silently completes when no columns are missing
- Integrated into app.py lifespan: called after `create_all`, inside the `sqlite` block, via `await conn.run_sync(sync_sqlite_columns)`
- TDD green: all 7 tests PASS
- Files created: backend/codehive/db/sync_columns.py, backend/tests/test_sqlite_column_sync.py
- Files modified: backend/codehive/api/app.py
- Tests added: 7
  1. Missing session columns (role, task_id, pipeline_step) are detected and added
  2. Existing columns are not touched when schema is complete
  3. Server defaults are applied (tasks.pipeline_status defaults to 'backlog')
  4. Multiple tables with missing columns are all synced
  5. TDD bug reproduction: ORM query fails before sync, succeeds after, old data preserved
  6. Logging: added columns are logged at INFO level
  7. Logging: no output when nothing is missing
- Build results: 2381 tests pass, 3 skipped, 0 fail, ruff clean
- Known limitations: SQLite only (by design); only handles additive column changes (no DROP/RENAME)

### [QA] 2026-03-28 10:30
- Tests: 7 passed, 0 failed (test_sqlite_column_sync.py)
- Full suite: 2381 passed, 3 skipped, 0 failed
- Ruff check: clean
- Ruff format: clean (295 files already formatted)
- Acceptance criteria:
  1. `sync_sqlite_columns()` helper exists in `backend/codehive/db/sync_columns.py`: PASS
  2. Uses `inspect()` to compare model metadata vs actual DB columns: PASS
  3. Executes `ALTER TABLE ADD COLUMN` with correct SQLite types via `column.type.compile(dialect=dialect)`: PASS
  4. Server defaults included in ALTER statement when present: PASS
  5. Nullable columns without server_default added as NULL-able: PASS
  6. Existing data preserved (purely additive, no DROP TABLE): PASS
  7. Called in lifespan after `create_all`, SQLite only: PASS
  8. Each added column logged at INFO level: PASS
  9. No unnecessary logging when nothing missing: PASS
  10. TDD bug reproduction test exists and verifies red-green cycle: PASS
  11. All existing tests continue to pass: PASS
  12. Lint clean: PASS
- VERDICT: PASS

### [PM] 2026-03-28 11:00
- Reviewed diff: 3 files changed (sync_columns.py new, test_sqlite_column_sync.py new, app.py +3 lines)
- Results verified: real data present -- 7 tests exercise missing-column detection, ALTER TABLE execution, server defaults, multi-table sync, TDD red-green cycle, and logging behavior
- Acceptance criteria: all 12 met
  1. sync_sqlite_columns() exists in backend/codehive/db/sync_columns.py: MET
  2. Uses inspect() to compare model metadata vs physical columns: MET
  3. ALTER TABLE ADD COLUMN with correct types via column.type.compile(): MET
  4. Server defaults included when present: MET
  5. Nullable columns added as NULL-able (no NOT NULL without DEFAULT): MET
  6. Purely additive -- no DROP, no recreate: MET
  7. Called in lifespan after create_all, SQLite-only guard: MET
  8. INFO-level logging per added column: MET
  9. Silent when nothing missing: MET
  10. TDD bug reproduction test (red-green): MET
  11. All 2381 existing tests pass: MET
  12. Ruff clean: MET
- Follow-up issues created: none needed
- VERDICT: ACCEPT
