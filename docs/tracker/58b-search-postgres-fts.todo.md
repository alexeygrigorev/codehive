# 58b: PostgreSQL Full-Text Search Optimization

## Description
Add PostgreSQL-specific full-text search (tsvector/tsquery) to the search backend. Issue 58a implemented search using ILIKE for SQLite compatibility. This issue adds the Alembic migration for tsvector columns and GIN indexes, and upgrades the search service to use ts_rank/ts_headline when running on PostgreSQL while preserving the ILIKE fallback for SQLite tests.

## Scope
- Alembic migration adding `search_vector` (tsvector) columns to sessions, messages, issues, events tables
- GIN indexes on all `search_vector` columns
- Database triggers or application-level logic to keep search_vector in sync on INSERT/UPDATE
- Update `backend/codehive/core/search.py` to detect PostgreSQL and use `plainto_tsquery()`, `ts_rank()`, `ts_headline()` instead of ILIKE
- Preserve ILIKE fallback for SQLite test compatibility

## Acceptance Criteria

- [ ] Alembic migration file exists under `backend/codehive/db/migrations/versions/` adding tsvector columns and GIN indexes to sessions, messages, issues, events tables
- [ ] `search_vector` columns are populated via triggers or application logic on INSERT/UPDATE
- [ ] Search service uses `ts_rank()` for relevance scoring on PostgreSQL
- [ ] Search service uses `ts_headline()` for snippet generation on PostgreSQL
- [ ] ILIKE fallback still works -- `uv run pytest tests/test_search.py -v` passes without PostgreSQL
- [ ] Integration test with PostgreSQL demonstrates ranked results (manual verification acceptable)

## Dependencies
- Depends on: #58a (search backend -- done)
