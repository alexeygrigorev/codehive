# 58b: PostgreSQL Full-Text Search Optimization

## Description
Add PostgreSQL-specific full-text search (tsvector/tsquery) to the search backend. Issue 58a implemented search using ILIKE for SQLite compatibility. This issue adds the Alembic migration for tsvector columns and GIN indexes, and upgrades the search service to use ts_rank/ts_headline when running on PostgreSQL while preserving the ILIKE fallback for SQLite tests.

## Scope
- Alembic migration adding `search_vector` (tsvector) columns to sessions, messages, issues, events tables
- GIN indexes on all `search_vector` columns
- Database triggers (preferred) or application-level logic to keep `search_vector` in sync on INSERT/UPDATE
- Update `backend/codehive/core/search.py` to detect the database dialect at query time and use `plainto_tsquery()`, `ts_rank()`, `ts_headline()` instead of ILIKE when running on PostgreSQL
- Preserve ILIKE fallback for SQLite -- all existing tests in `backend/tests/test_search.py` must continue to pass unchanged on SQLite
- No changes to the API routes or Pydantic schemas (the response format stays the same)

## Acceptance Criteria

- [x] New Alembic migration file exists under `backend/codehive/db/migrations/versions/` that adds a `search_vector` tsvector column to each of: `sessions`, `messages`, `issues`, `events`
- [x] The migration creates a GIN index on `search_vector` for each of those four tables
- [x] The migration creates PostgreSQL triggers (via `CREATE TRIGGER` / `tsvector_update_trigger` or custom trigger functions) that automatically populate `search_vector` on INSERT and UPDATE, specifically:
  - `sessions.search_vector` from `name`
  - `messages.search_vector` from `content`
  - `issues.search_vector` from `title` and `description`
  - `events.search_vector` from `type`
- [x] The migration `downgrade()` drops the triggers, indexes, and columns cleanly
- [x] `backend/codehive/core/search.py` detects the database dialect (e.g. via `db.bind.dialect.name == "postgresql"`) and branches:
  - **PostgreSQL path:** uses `func.plainto_tsquery()` to parse user query, `search_vector.op('@@')` for matching, `func.ts_rank()` for scoring, and `func.ts_headline()` for snippet generation
  - **SQLite path:** uses existing ILIKE logic unchanged
- [x] On PostgreSQL, search results are ordered by `ts_rank` descending (relevance), not just `created_at`
- [x] On PostgreSQL, snippets contain highlighted matches (ts_headline output with `StartSel`/`StopSel` markers, e.g. `<b>...</b>`)
- [x] `search_session_history()` also uses the PostgreSQL FTS path when available
- [x] All 23 existing tests in `backend/tests/test_search.py` pass without modification: `uv run pytest backend/tests/test_search.py -v` (SQLite fallback path)
- [x] `uv run ruff check backend/` and `uv run ruff format --check backend/` pass cleanly
- [x] At least 3 new PostgreSQL-specific tests exist (can be in a separate file, e.g. `backend/tests/test_search_postgres.py`, or as marked/skipped tests in the existing file) that are skipped when PostgreSQL is unavailable but document the expected behavior:
  - FTS matching via tsvector returns results for stemmed words (e.g. searching "running" matches "run")
  - `ts_rank` produces varying scores (not all 1.0) for results with different relevance
  - `ts_headline` output contains highlight markers around matched terms

## Test Scenarios

### Unit: Dialect detection (core/search.py)
- Verify that with a SQLite session, the search function takes the ILIKE path (existing tests cover this implicitly)
- Verify that the dialect detection branch exists and selects PostgreSQL path for `dialect.name == "postgresql"`

### Unit: PostgreSQL FTS path (requires PostgreSQL or mocking)
- Insert sessions with names "running fast" and "unrelated topic"; search for "run"; verify the stemmed match is found via tsvector
- Insert multiple matching records with varying content lengths/relevance; verify `ts_rank` produces different scores (not all identical)
- Search for a term; verify the snippet from `ts_headline` contains `<b>term</b>` markers (or configured StartSel/StopSel)
- Verify multi-word queries work with `plainto_tsquery` (each word ANDed)

### Unit: search_session_history PostgreSQL path
- Same FTS behavior within a single session's messages and events when running on PostgreSQL

### Integration: Alembic migration
- `alembic upgrade head` on a PostgreSQL database succeeds without errors
- `alembic downgrade -1` cleanly removes the tsvector columns, triggers, and indexes
- After migration, inserting a row into `sessions` automatically populates `search_vector`

### Regression: SQLite fallback
- All 23 existing tests pass with no changes (the full existing test suite is the regression suite)

## Dependencies
- Depends on: #58a (search backend with ILIKE fallback -- done)

## Implementation Notes

### Dialect detection pattern
The search service receives an `AsyncSession`. To detect the dialect, use:
```python
dialect_name = db.bind.dialect.name  # "postgresql" or "sqlite"
```

### tsvector column definition
In the Alembic migration (not in SQLAlchemy models, since the models must remain SQLite-compatible):
```python
from sqlalchemy.dialects.postgresql import TSVECTOR
op.add_column('sessions', sa.Column('search_vector', TSVECTOR(), nullable=True))
op.create_index('ix_sessions_search_vector', 'sessions', ['search_vector'], postgresql_using='gin')
```

### Trigger example
```sql
CREATE FUNCTION sessions_search_vector_update() RETURNS trigger AS $$
BEGIN
  NEW.search_vector := to_tsvector('english', coalesce(NEW.name, ''));
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER sessions_search_vector_trigger
  BEFORE INSERT OR UPDATE ON sessions
  FOR EACH ROW EXECUTE FUNCTION sessions_search_vector_update();
```

### Do NOT modify SQLAlchemy models
The `search_vector` column should exist only in the Alembic migration and PostgreSQL database, not in `backend/codehive/db/models.py`. The models must remain SQLite-compatible for the test suite. The search service accesses `search_vector` via raw SQL or `text()` / `column()` constructs when on PostgreSQL.

### ts_headline configuration
Use `StartSel='<b>', StopSel='</b>'` for snippet highlighting so the API consumers can render highlights.

## Log

### [SWE] 2026-03-16 14:30
- Implemented PostgreSQL FTS support with dialect detection in search.py
- Added `_is_postgresql()` helper that checks `db.bind.dialect.name == "postgresql"`
- Both `search()` and `search_session_history()` now branch: PostgreSQL uses `plainto_tsquery`, `ts_rank`, `ts_headline` with `column("search_vector")`; SQLite keeps ILIKE unchanged
- PostgreSQL path orders by `ts_rank` descending (relevance); SQLite path keeps `created_at` descending
- PostgreSQL snippets come directly from `ts_headline` with `StartSel='<b>', StopSel='</b>'`; SQLite snippets use existing `_truncate_snippet()`
- Created Alembic migration `g7b8c9d0e1f2` that adds `search_vector` tsvector column, GIN index, trigger function, and BEFORE INSERT OR UPDATE trigger for all 4 tables (sessions, messages, issues, events), plus backfill of existing rows
- Migration `downgrade()` cleanly drops triggers, functions, indexes, and columns
- Models (models.py) NOT modified -- tsvector columns exist only in migration/PostgreSQL
- Files modified:
  - `backend/codehive/core/search.py` -- added FTS helpers and dual-path logic
  - `backend/codehive/db/migrations/versions/g7b8c9d0e1f2_add_fts_tsvector_columns.py` -- new migration
  - `backend/tests/test_search_postgres.py` -- new test file
- Tests added: 14 tests (11 pass, 3 skipped for live PostgreSQL)
  - 3 dialect detection tests (postgresql, sqlite, other)
  - 3 FTS helper compile tests (plainto_tsquery, ts_rank, ts_headline)
  - 3 PostgreSQL integration tests (skipped without live PG): stemming, ranking, highlighting
  - 2 mocked search path tests (verify FTS path taken on postgresql dialect)
  - 3 snippet truncation regression tests
- Build results: 23 existing tests pass, 14 new tests (11 pass, 3 skipped), ruff clean
- Known limitations: PostgreSQL integration tests require a live PostgreSQL instance with the migration applied; they are skipped by default

### [QA] 2026-03-16 15:10
- Tests: 1343 passed, 3 skipped (full suite), 0 failed
- Ruff check: clean
- Ruff format: clean
- Acceptance criteria:
  1. Alembic migration file exists at `backend/codehive/db/migrations/versions/g7b8c9d0e1f2_add_fts_tsvector_columns.py` adding `search_vector` tsvector to sessions, messages, issues, events: PASS
  2. Migration creates GIN index on `search_vector` for all four tables: PASS
  3. Migration creates PostgreSQL triggers (BEFORE INSERT OR UPDATE) that populate `search_vector` from correct source columns (sessions.name, messages.content, issues.title+description, events.type): PASS
  4. Migration `downgrade()` drops triggers, functions, indexes, and columns cleanly: PASS
  5. `search.py` detects dialect via `db.bind.dialect.name == "postgresql"` and branches (PostgreSQL: plainto_tsquery/@@/ts_rank/ts_headline; SQLite: ILIKE unchanged): PASS
  6. PostgreSQL path orders by `ts_rank` descending (relevance): PASS
  7. PostgreSQL snippets use `ts_headline` with `StartSel='<b>', StopSel='</b>'`: PASS
  8. `search_session_history()` also uses PostgreSQL FTS path when available: PASS
  9. All 23 existing tests in `test_search.py` pass without modification: PASS (file has zero diff, all 23 pass)
  10. `ruff check` and `ruff format --check` pass cleanly: PASS
  11. At least 3 new PostgreSQL-specific tests exist (stemming, ranking, highlighting) skipped without PG: PASS (3 skipped tests in test_search_postgres.py)
  12. No changes to API routes or Pydantic schemas: PASS (git diff shows no changes to route/schema files)
- VERDICT: PASS

### [PM] 2026-03-16 15:45
- Reviewed diff: 4 files changed (1 modified, 2 new, 1 deleted todo)
  - `backend/codehive/core/search.py` -- 207 insertions, 99 deletions (dual-path FTS/ILIKE logic)
  - `backend/codehive/db/migrations/versions/g7b8c9d0e1f2_add_fts_tsvector_columns.py` -- new migration (69 lines)
  - `backend/tests/test_search_postgres.py` -- new test file (261 lines, 14 tests)
  - `docs/tracker/58b-search-postgres-fts.todo.md` -- deleted (replaced by groomed in-progress file)
- Results verified: real test data present (1343 passed, 3 skipped, ruff clean); FTS constructs verified via compile-to-PostgreSQL-dialect tests
- Code quality: clean, well-structured dual-path branching; migration is concise with data-driven table loop; models.py untouched as specified; `column("search_vector")` correctly avoids SQLite model contamination
- No changes to API routes or Pydantic schemas confirmed (zero diff)
- Existing test_search.py has zero diff -- full regression safety
- Acceptance criteria: all 12 met
- Follow-up issues created: none needed
- VERDICT: ACCEPT
