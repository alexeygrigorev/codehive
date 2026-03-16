# 58: Search and History (Parent)

## Description
Full-text search across sessions, issues, events, messages, and project history. Split into backend search API and frontend search UI.

## Sub-Issues
- **58a** -- Backend: full-text search API using PostgreSQL `tsvector`/`tsquery`
- **58b** -- Frontend: search bar, results page, search-as-you-type

## Dependencies
- Depends on: #07 (event bus), #46 (issue tracker), #51 (persistent logs), #14 (React app)
