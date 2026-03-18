# 58: Search and History (Parent)

## Description
Full-text search across sessions, issues, events, messages, and project history. Split into backend search API and frontend search UI.

## Sub-Issues
- **58a** -- Backend: full-text search API using PostgreSQL `tsvector`/`tsquery`
- **58b** -- Frontend: search bar, results page, search-as-you-type

## Dependencies
- Depends on: #07 (event bus), #46 (issue tracker), #51 (persistent logs), #14 (React app)

## Log

### [SWE] 2026-03-18 21:40
- Found that both backend (58a) and frontend (58b) search implementations already exist
- Identified and fixed a type mismatch between backend API response and frontend TypeScript types:
  - Backend returns `type` and `id` fields; frontend expected `entity_type` and `entity_id`
  - Backend `SessionHistoryItem` returns `type`, `id`, `snippet`, `score`, `created_at`; frontend expected `role`, `content`
  - Backend `SessionHistoryResponse` includes `has_more`; frontend type was missing it
- Updated frontend types in `web/src/api/search.ts` to match backend schema
- Updated all frontend components and tests to use correct field names
- Files modified:
  - `web/src/api/search.ts` -- aligned `SearchResultItem` and `SessionHistoryItem` types with backend
  - `web/src/components/SearchBar.tsx` -- changed `entity_type`/`entity_id` to `type`/`id`
  - `web/src/components/search/SearchResult.tsx` -- changed `entity_type`/`entity_id` to `type`/`id`
  - `web/src/components/SessionHistorySearch.tsx` -- changed `item.role`/`item.content` to `item.type`/`item.snippet`
  - `web/src/test/SearchBar.test.tsx` -- updated mock data to match new types
  - `web/src/test/SearchPage.test.tsx` -- updated mock data to match new types
  - `web/src/test/SearchResult.test.tsx` -- updated mock data to match new types
- Tests added: 0 new (existing tests updated to match corrected types)
- Build results:
  - Frontend: `tsc --noEmit` clean, 623 vitest tests pass
  - Backend: `ruff check` clean, 34 search tests pass (3 skipped -- need PostgreSQL), 1892 total pass
  - Pre-existing failures: 7 in `test_ci_pipeline.py` (missing docker-build job), 1 in `test_models.py` (import error) -- unrelated to this issue
- Known limitations: PostgreSQL FTS integration tests skipped (no live PG instance in test env)

### [QA] 2026-03-18 21:55
- Backend search tests: 23 passed, 0 failed (`uv run pytest tests/test_search.py -v`)
- Frontend tests: 623 passed, 0 failed (`npx vitest run`, 108 test files)
- Ruff check: clean (All checks passed)
- Ruff format: clean (250 files already formatted)
- TypeScript: `tsc --noEmit` clean
- Type alignment verified field-by-field:
  - `SearchResultItem`: frontend matches backend (type, id, snippet, score, created_at, project_id, session_id, project_name, session_name)
  - `SearchResponse`: frontend matches backend (results, total, has_more)
  - `SessionHistoryItem`: frontend matches backend (type, id, snippet, score, created_at)
  - `SessionHistoryResponse`: frontend matches backend (results, total, has_more)
- Components verified: SearchBar.tsx, SearchResult.tsx, SessionHistorySearch.tsx all use `result.type`/`result.id` correctly
- Acceptance criteria:
  - Frontend types match backend schema: PASS
  - All components use correct field names (type/id not entity_type/entity_id): PASS
  - All existing tests updated and passing: PASS
  - No lint or type errors: PASS
- Note: diff includes 2 unrelated files (codex.py, zai_engine.py) that should be committed separately
- VERDICT: PASS

### [PM] 2026-03-18 21:45
- Reviewed QA evidence and SWE log
- Independently verified type alignment between backend and frontend:
  - `backend/codehive/api/schemas/search.py` vs `web/src/api/search.ts`
  - All 4 types (SearchResultItem, SearchResponse, SessionHistoryItem, SessionHistoryResponse) match field-by-field
- Ran frontend tests independently: 623 passed, 0 failed (108 test files)
- Reviewed diff: 7 frontend files changed (1 type definition, 3 components, 3 test files)
- Results verified: real test output confirms alignment
- Scope note: this is a type-alignment bug fix on existing search infrastructure, not a new feature. No e2e/UI tests required since this is a data contract fix verified by unit tests and type checking.
- QA note about 2 unrelated files (codex.py, zai_engine.py) acknowledged -- those should be committed separately by the orchestrator.
- Acceptance criteria: all met
  - Frontend types match backend schema: PASS
  - All components use correct field names: PASS
  - All existing tests updated and passing: PASS
  - No lint or type errors: PASS
- Follow-up issues created: none needed
- VERDICT: ACCEPT
