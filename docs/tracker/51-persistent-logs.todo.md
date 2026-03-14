# 51: Persistent Session Logs

## Description
Ensure all session activity is durably stored for debugging, performance analysis, and future agent training. Store agent messages, tool calls with arguments and results, file changes, terminal output, and diff history in a queryable format.

## Scope
- `backend/codehive/core/logs.py` -- Log storage service: structured logging of all session actions to DB
- `backend/codehive/api/routes/logs.py` -- Endpoints for querying session logs (with filters: type, time range, pagination)
- `backend/codehive/engine/native.py` -- Extend to log all tool calls with full arguments and results
- `backend/tests/test_logs.py` -- Log storage and query tests

## Endpoints
- `GET /api/sessions/{session_id}/logs` -- Query session logs (filter by type, time range)
- `GET /api/sessions/{session_id}/logs/export` -- Export full session log (JSON)

## Dependencies
- Depends on: #07 (events table as the base storage)
- Depends on: #09 (engine adapter for tool call logging)
