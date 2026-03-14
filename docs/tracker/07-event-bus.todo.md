# 07: Event Bus

## Description
Redis pub/sub event bus for real-time session events, with persistent storage in the events table.

## Scope
- `backend/codehive/core/events.py` — Event bus (publish/subscribe via Redis pub/sub)
- `backend/codehive/api/ws.py` — WebSocket endpoint that subscribes to session events
- `backend/codehive/api/routes/events.py` — REST endpoint to query past events
- `backend/tests/test_events.py` — Event bus tests

## Event types
`message.created`, `tool.call.started`, `tool.call.finished`, `file.changed`, `diff.updated`, `task.started`, `task.completed`, `approval.required`, `session.status_changed`

## Behavior
- Publishing an event: writes to DB + publishes to Redis channel `session:{id}:events`
- WebSocket clients subscribe to a session's channel and receive events in real-time
- REST endpoint returns historical events for a session (with pagination)

## Dependencies
- Depends on: #05 (needs sessions), #02 (needs Redis)
