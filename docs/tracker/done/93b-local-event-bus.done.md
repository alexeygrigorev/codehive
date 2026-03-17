# Issue #93b: In-memory LocalEventBus (no Redis required)

Parent: #93 (Lightweight SQLite mode)

## Problem

The `EventBus` class requires a Redis connection in its constructor. The WebSocket handler (`ws.py`) also directly creates a Redis connection for pub/sub. When Redis is not available, there is no way to run the backend server -- it fails on startup or on any event publish. The `_NoOpEventBus` in `code_app.py` silently discards events, which is wrong for WebSocket streaming.

## Scope

Create a `LocalEventBus` that uses asyncio primitives for in-memory pub/sub, and make the WebSocket handler work with it. Auto-select based on whether `REDIS_URL` is configured.

## Requirements

- [ ] Create `LocalEventBus` class in `codehive/core/events.py` that implements the same interface as `EventBus`
- [ ] `LocalEventBus` uses `asyncio` primitives (e.g., dict of `asyncio.Queue` per channel) for pub/sub
- [ ] `LocalEventBus.publish()` persists events to the database (same as `EventBus`) AND broadcasts to in-memory subscribers
- [ ] `LocalEventBus` supports `subscribe(session_id)` returning an async iterator of events (for WebSocket consumption)
- [ ] Add a factory function `create_event_bus(redis_url, ...)` that returns `EventBus` if `redis_url` is set, `LocalEventBus` otherwise
- [ ] Update `ws.py` to work with both bus types: use the event bus's subscribe method instead of direct Redis pub/sub
- [ ] Update `_NoOpEventBus` in `code_app.py` to use `LocalEventBus` (or keep it as-is since the TUI doesn't need pub/sub)
- [ ] The backend server starts and WebSocket streaming works with `CODEHIVE_REDIS_URL=""` (empty = no Redis)

## Design

```python
class LocalEventBus:
    """In-process event bus using asyncio for single-process deployments."""

    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, db: AsyncSession, session_id: uuid.UUID,
                      event_type: str, data: dict, redactor=None) -> Event:
        # Persist to DB (same as EventBus)
        event = Event(...)
        db.add(event)
        await db.commit()
        # Broadcast to in-memory subscribers
        message = json.dumps({...})
        for queue in self._subscribers.get(session_id, []):
            queue.put_nowait(message)
        return event

    @asynccontextmanager
    async def subscribe(self, session_id: uuid.UUID):
        queue = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        try:
            yield queue
        finally:
            self._subscribers[session_id].remove(queue)
```

## Dependencies

- None (can be done in parallel with #93a)

## Acceptance Criteria

- [ ] `uv run pytest tests/ -v` passes (no regressions)
- [ ] `LocalEventBus` persists events to the database
- [ ] `LocalEventBus` broadcasts events to all subscribers for a session
- [ ] Multiple subscribers to the same session each receive all events
- [ ] Unsubscribing removes the subscriber cleanly (no memory leak)
- [ ] `create_event_bus("")` returns `LocalEventBus`; `create_event_bus("redis://...")` returns `EventBus`
- [ ] WebSocket handler uses the event bus subscribe interface (not direct Redis)
- [ ] `uv run ruff check` passes clean
- [ ] 5+ new unit tests for `LocalEventBus`

## Test Scenarios

### Unit: LocalEventBus
- Publish an event, verify it is persisted to the database
- Subscribe to a session, publish an event, verify subscriber receives it
- Two subscribers to the same session both receive the same event
- Unsubscribe, publish an event, verify the unsubscribed queue does NOT receive it
- Publish to session A, verify subscriber to session B does NOT receive it

### Unit: Factory
- `create_event_bus("")` returns `LocalEventBus`
- `create_event_bus("redis://localhost:6379")` returns `EventBus`

### Integration: WebSocket with LocalEventBus
- Connect WebSocket to session, publish event via LocalEventBus, verify WebSocket receives the event message

## Log

### [SWE] 2026-03-17 12:00
- Implemented `LocalEventBus` class in `codehive/core/events.py` using `asyncio.Queue`-based pub/sub with `defaultdict(list)` of subscribers keyed by session_id
- Extracted `_serialize_event()` helper shared by both `EventBus` and `LocalEventBus`
- Added `subscribe()` async context manager to both `EventBus` (wrapping Redis pub/sub) and `LocalEventBus` (using asyncio queues)
- Added `create_event_bus(redis_url)` factory function: returns `EventBus` if redis_url is non-empty, `LocalEventBus` otherwise
- Updated `ws.py` to use `create_event_bus()` and the bus's `subscribe()` interface instead of direct Redis pub/sub
- Kept `_NoOpEventBus` in `code_app.py` as-is (TUI doesn't need real pub/sub, it runs the engine directly)
- Memory leak prevention: empty subscriber lists are cleaned up via `del self._subscribers[session_id]` when last subscriber leaves
- Files modified: `backend/codehive/core/events.py`, `backend/codehive/api/ws.py`
- Files created: `backend/tests/test_local_event_bus.py`
- Tests added: 11 tests (6 publish/subscribe, 2 get_events, 3 factory)
- Build results: 1706 pass, 0 fail from my changes (26 pre-existing errors in test_archetypes/test_roles), ruff clean on modified files
