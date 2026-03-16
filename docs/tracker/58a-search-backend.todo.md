# 58a: Search Backend API

## Description
Implement full-text search across sessions, messages, issues, and events using PostgreSQL full-text search capabilities (tsvector/tsquery). Provide a unified search API endpoint.

## Implementation Plan

### 1. Database changes
- Alembic migration to add `tsvector` columns:
  - `sessions.search_vector` -- generated from `name`
  - `messages.search_vector` -- generated from `content`
  - `issues.search_vector` -- generated from `title` + `description`
  - `events.search_vector` -- generated from `data` (JSONB text extraction)
- GIN indexes on all `search_vector` columns for fast lookup
- Database trigger or application-level update to keep vectors in sync

### 2. Search service
- `backend/codehive/core/search.py`
- `async def search(db, query, filters) -> SearchResults`
- Filters: `entity_type` (session/message/issue/event), `project_id`, `session_id`, `date_range`
- Uses `plainto_tsquery()` for user-friendly query parsing
- Returns ranked results with `ts_rank()` scoring
- Results include: entity type, entity ID, matched text snippet (with `ts_headline()`), project name, timestamp

### 3. API endpoint
- `GET /api/search?q={query}&type={entity_type}&project_id={id}&limit={n}&offset={n}`
- Returns: `{results: [{type, id, snippet, project_name, session_name, timestamp, score}], total, has_more}`
- `backend/codehive/api/routes/search.py`
- `backend/codehive/api/schemas/search.py`

### 4. Session history endpoint
- `GET /api/sessions/{id}/history?q={query}&limit={n}&offset={n}`
- Searches within a single session's messages and events
- Useful for finding specific actions/messages in long sessions

## Acceptance Criteria

- [ ] Alembic migration adds tsvector columns and GIN indexes to sessions, messages, issues, events
- [ ] `GET /api/search?q=auth` returns matching sessions, messages, and issues containing "auth"
- [ ] Results are ranked by relevance (ts_rank)
- [ ] Results include text snippets with highlighted matches
- [ ] Filtering by entity type works: `?type=message` returns only messages
- [ ] Filtering by project works: `?project_id={id}` scopes results to one project
- [ ] Pagination works: `?limit=10&offset=20` returns correct page
- [ ] `GET /api/sessions/{id}/history?q=test` searches within a session
- [ ] `uv run pytest tests/test_search.py -v` passes with 8+ tests

## Test Scenarios

### Unit: Search service
- Insert messages with known text, search for keyword, verify matches returned
- Search with no matches, verify empty results
- Search with type filter, verify only matching entity type returned
- Search with project filter, verify scoping works
- Verify results are ordered by relevance score

### Unit: Snippets
- Search for "authentication", verify snippet contains highlighted match
- Verify snippet is truncated to reasonable length

### Integration: API endpoint
- GET `/api/search?q=test`, verify 200 response with correct schema
- GET `/api/search?q=test&type=issue`, verify only issues returned
- GET `/api/sessions/{id}/history?q=error`, verify session-scoped results

## Dependencies
- Depends on: #03 (DB models), #07 (events table), #46 (issues table)
