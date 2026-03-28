# 155 -- Usage-aware agent spawning: switch engines when limits approach

## Problem

When an engine (e.g. `claude_code`) hits rate limits mid-pipeline, the orchestrator keeps trying to spawn sub-agents on that engine and fails. There is no automatic failover to another available engine. The `_resolve_sub_agent_engine` method currently returns a static engine -- it does not consult rate-limit data at all.

## Dependencies

- #122 `usage-limits-and-model-breakdown.done.md` -- RateLimitSnapshot + ModelUsageSnapshot models and persist_usage_event
- #128 `engine-persist-rate-limit-events.done.md` -- engines write rate_limit.updated events to DB
- #139 `orchestrator-auto-pipeline.done.md` -- OrchestratorService pipeline loop
- #153 `orchestrator-engine-selection.done.md` -- sub_agent_engines config + _resolve_sub_agent_engine

All dependencies are `.done.md`.

## User Stories

### Story: Engine hits rate limit, orchestrator fails over silently

1. The orchestrator is running a pipeline for project P with `sub_agent_engines: ["claude_code", "codex_cli"]`
2. A `rate_limit.updated` event arrives for `claude_code` with `utilization: 0.95` (above the 80% threshold)
3. The orchestrator marks `claude_code` as throttled with a cooldown derived from `resets_at`
4. The next pipeline step needs to spawn a sub-agent
5. `_resolve_sub_agent_engine` skips `claude_code` (throttled) and returns `codex_cli`
6. The sub-agent session is created with engine `codex_cli`
7. Pipeline continues without interruption

### Story: All engines throttled, orchestrator waits and retries

1. Both `claude_code` and `codex_cli` are throttled
2. The orchestrator attempts to spawn a sub-agent
3. `_resolve_sub_agent_engine` finds no available engine
4. The orchestrator waits using exponential backoff (1s, 2s, 4s... up to 60s)
5. After the `resets_at` time passes for `claude_code`, its throttle expires
6. Next retry returns `claude_code` as available
7. Pipeline resumes

### Story: Throttle state expires automatically

1. `claude_code` was throttled at 14:00 with `resets_at` = 14:05 (epoch)
2. At 14:06, the orchestrator needs to spawn a sub-agent
3. `_resolve_sub_agent_engine` checks the throttle state, sees it expired
4. `claude_code` is returned as the preferred engine (first in list)
5. No failover needed

### Story: API shows throttle status

1. User opens the Codehive dashboard and navigates to the project orchestrator view
2. The GET `/api/projects/{id}/orchestrator/status` endpoint now includes an `engine_status` map
3. Each engine shows: `available: true/false`, `throttled_until: ISO timestamp or null`, `reason: string`
4. User sees that `claude_code` is throttled until 14:05, `codex_cli` is available

## Acceptance Criteria

- [ ] New `EngineThrottleTracker` class (or similar) in `backend/codehive/core/` that manages per-engine throttle state
- [ ] `EngineThrottleTracker.mark_throttled(engine, resets_at)` records throttle with expiry based on `resets_at` epoch timestamp
- [ ] `EngineThrottleTracker.is_available(engine)` returns `True` when not throttled or throttle has expired
- [ ] `EngineThrottleTracker.get_available(engines: list[str])` returns the first non-throttled engine or `None`
- [ ] `OrchestratorService._resolve_sub_agent_engine` is updated to consult the throttle tracker instead of returning a static engine
- [ ] When a `rate_limit.updated` event arrives with `utilization >= 0.80`, the engine is marked as throttled
- [ ] Throttle threshold (default 0.80) is configurable via `OrchestratorService.config["throttle_utilization_threshold"]`
- [ ] When all engines are throttled, spawning retries with exponential backoff (1s base, 60s max, 3 retries before raising)
- [ ] Throttle state expires automatically when `resets_at` timestamp is in the past
- [ ] `OrchestratorService.get_status()` includes `engine_status` dict showing throttle state per configured engine
- [ ] `GET /api/projects/{id}/orchestrator/status` response includes the engine_status data
- [ ] `uv run pytest tests/ -v` passes with 8+ new tests covering throttle tracker and orchestrator integration
- [ ] `uv run ruff check` is clean

## Technical Notes

### Where to put the throttle tracker

Create `backend/codehive/core/engine_throttle.py` with an `EngineThrottleTracker` class. This is an in-memory tracker (not DB-persisted) since throttle state is transient and only relevant to a running orchestrator instance. Use `time.monotonic()` for expiry comparisons to avoid clock skew issues, but store the wall-clock `resets_at` for API display.

### Integration points

1. **`_resolve_sub_agent_engine`** (orchestrator_service.py line 641): Replace the static `engines[0]` logic with `self._throttle_tracker.get_available(engines)`. If `None`, run the backoff/retry loop.

2. **Rate-limit event ingestion**: After `persist_usage_event` writes a `RateLimitSnapshot`, the orchestrator needs to be notified. Two options:
   - **Option A (recommended)**: In `_default_spawn_and_run` or the engine event callback, check if the event is `rate_limit.updated` and call `self._throttle_tracker.mark_throttled(engine, resets_at)` directly.
   - **Option B**: Poll `RateLimitSnapshot` from DB before each spawn. Simpler but adds DB queries.

3. **`get_status()`** (orchestrator_service.py line 689): Add `engine_status` to the returned dict.

### Retry strategy when all engines are throttled

```python
async def _resolve_sub_agent_engine_with_retry(self) -> str:
    engines = self.config.get("sub_agent_engines", []) or [self.config["engine"]]
    max_retries = 3
    base_delay = 1.0
    max_delay = 60.0

    for attempt in range(max_retries + 1):
        available = self._throttle_tracker.get_available(engines)
        if available:
            return available
        if attempt < max_retries:
            delay = min(base_delay * (2 ** attempt), max_delay)
            await asyncio.sleep(delay)

    raise RuntimeError("All engines throttled after retries exhausted")
```

### Existing models to leverage

- `RateLimitSnapshot` already stores `utilization`, `resets_at`, and `rate_limit_type` -- the throttle tracker reads these fields from incoming events.
- `persist_usage_event` in `usage.py` already handles `rate_limit.updated` events -- the orchestrator hooks into the same event data.

### What is NOT in scope

- Persisting throttle state to the database (it is ephemeral, in-memory only)
- Changing the `persist_usage_event` function itself
- Adding new DB models or migrations
- Frontend UI changes (the API response change is sufficient; frontend display is a separate issue)

## Test Scenarios

### Unit: EngineThrottleTracker

- `mark_throttled("claude_code", future_epoch)` then `is_available("claude_code")` returns `False`
- `mark_throttled("claude_code", past_epoch)` then `is_available("claude_code")` returns `True` (already expired)
- `get_available(["claude_code", "codex_cli"])` returns `"codex_cli"` when `claude_code` is throttled
- `get_available(["claude_code", "codex_cli"])` returns `None` when both are throttled
- `get_available(["claude_code"])` returns `"claude_code"` when not throttled
- Throttle state expires: mark throttled with short TTL, sleep briefly, verify `is_available` returns `True`

### Unit: _resolve_sub_agent_engine with throttle awareness

- With no throttled engines, returns first engine from `sub_agent_engines`
- With first engine throttled, returns second engine
- With all engines throttled and retries exhausted, raises `RuntimeError`

### Integration: Orchestrator pipeline with rate-limit event

- Simulate a `rate_limit.updated` event with `utilization=0.95` during pipeline execution
- Verify the next `_default_spawn_and_run` call uses a different engine
- Verify `get_status()` includes `engine_status` with throttle info

### Integration: API endpoint

- `GET /api/projects/{id}/orchestrator/status` returns `engine_status` field
- Throttled engine shows `available: false` with `throttled_until` timestamp
- Non-throttled engine shows `available: true`

## Log

### [SWE] 2026-03-28 12:00
- Created `backend/codehive/core/engine_throttle.py` with `EngineThrottleTracker` class
  - `mark_throttled(engine, resets_at)` records throttle with expiry based on `resets_at` epoch
  - `is_available(engine)` returns True when not throttled or expired (uses `time.monotonic()` for expiry)
  - `get_available(engines)` returns first non-throttled engine or None
  - `get_status()` returns dict with availability, throttled_until (ISO), and reason per engine
- Updated `backend/codehive/core/orchestrator_service.py`:
  - Added `_throttle_tracker` attribute (EngineThrottleTracker instance) to OrchestratorService
  - `_resolve_sub_agent_engine()` now consults throttle tracker to skip throttled engines
  - Added `_resolve_sub_agent_engine_with_retry()` with exponential backoff (1s, 2s, 4s; max 60s; 3 retries)
  - Added `handle_rate_limit_event(engine, event)` to process rate_limit.updated events with configurable threshold (default 0.80)
  - `_default_spawn_and_run` now uses the async retry wrapper
  - `get_status()` now includes `engine_status` dict showing throttle state per configured engine
- Updated `backend/codehive/api/routes/orchestrator.py`:
  - Added `EngineStatusEntry` Pydantic model
  - Added `engine_status` field to `OrchestratorResponse`
  - Status endpoint passes engine_status from service to response
- Files modified: `backend/codehive/core/engine_throttle.py` (new), `backend/codehive/core/orchestrator_service.py`, `backend/codehive/api/routes/orchestrator.py`
- Tests added: 24 new tests in `backend/tests/test_engine_throttle.py`
  - 9 unit tests for EngineThrottleTracker (throttle, expiry, get_available, get_status)
  - 3 unit tests for _resolve_sub_agent_engine with throttle awareness
  - 3 unit tests for _resolve_sub_agent_engine_with_retry (available, skip throttled, raises on all throttled)
  - 4 unit tests for handle_rate_limit_event (high/low utilization, custom threshold, zero resets_at)
  - 2 unit tests for get_status engine_status inclusion
  - 3 integration tests for API endpoint (includes engine_status, shows throttled, stopped has None)
- Build results: 74 tests pass (50 existing + 24 new), 0 fail, ruff clean
- Known limitations: None

### [QA] 2026-03-28 12:30
- Tests: 24 passed in test_engine_throttle.py, 50 passed in test_orchestrator_service.py, 0 failed
- Ruff: clean (check + format)
- Acceptance criteria:
  1. EngineThrottleTracker class in backend/codehive/core/engine_throttle.py: PASS
  2. mark_throttled(engine, resets_at) records throttle with expiry: PASS
  3. is_available(engine) returns True when not throttled or expired: PASS
  4. get_available(engines) returns first non-throttled or None: PASS
  5. _resolve_sub_agent_engine consults throttle tracker: PASS
  6. rate_limit.updated with utilization >= 0.80 throttles engine: PASS
  7. Threshold configurable via config["throttle_utilization_threshold"]: PASS
  8. All engines throttled -> exponential backoff (1s base, 60s max, 3 retries): PASS
  9. Throttle expires automatically when resets_at in past: PASS
  10. get_status() includes engine_status dict: PASS
  11. GET /api/orchestrator/status includes engine_status: PASS
  12. 8+ new tests: PASS (24 new tests)
  13. ruff check clean: PASS
- VERDICT: PASS

### [PM] 2026-03-28 13:00
- Reviewed diff: 3 files changed (1 new), plus 1 new test file (462 lines total)
  - `backend/codehive/core/engine_throttle.py` (new, 110 lines): clean dataclass + tracker class, monotonic clock for expiry, wall-clock for display
  - `backend/codehive/core/orchestrator_service.py`: throttle tracker instance, `_resolve_sub_agent_engine` consults tracker, `_resolve_sub_agent_engine_with_retry` with exp backoff, `handle_rate_limit_event` with configurable threshold, `get_status()` includes engine_status
  - `backend/codehive/api/routes/orchestrator.py`: `EngineStatusEntry` Pydantic model, `engine_status` field in response, status endpoint wired up
  - `backend/tests/test_engine_throttle.py` (new, 462 lines): 24 tests across 7 test classes
- Results verified: 24/24 tests pass, ruff clean, real test output confirmed
- Acceptance criteria: all 13 met
  1. EngineThrottleTracker class exists: MET
  2. mark_throttled records expiry: MET
  3. is_available checks expiry: MET
  4. get_available returns first non-throttled or None: MET
  5. _resolve_sub_agent_engine consults tracker: MET
  6. High utilization throttles engine: MET
  7. Configurable threshold (default 0.80): MET
  8. Exponential backoff (1s/2s/4s, 60s max, 3 retries, RuntimeError): MET
  9. Auto-expiry on resets_at in past: MET
  10. get_status() includes engine_status: MET
  11. API endpoint includes engine_status: MET
  12. 8+ new tests (24 actual): MET
  13. ruff check clean: MET
- Code quality notes: clean separation of concerns, monotonic clock avoids skew, docstrings present, no over-engineering
- Follow-up issues created: none needed
- VERDICT: ACCEPT
