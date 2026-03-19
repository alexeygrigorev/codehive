# Issue #128: Wire engine to persist rate_limit and model_usage events to DB

## Problem

Issue #122 added parsing of `rate_limit_event` and `modelUsage` from the Claude Code stream, plus DB models (`RateLimitSnapshot`, `ModelUsageSnapshot`), the `GET /api/usage/limits` API endpoint, and frontend UI. However, the event-processing loop that consumes engine events during live sessions does not persist `rate_limit.updated` or `usage.model_breakdown` events to the database.

Without this wiring, the plan limits data will never appear in the UI during normal operation -- it can only be inserted manually or via tests.

## Origin

Descoped from #122 (usage limits and per-model breakdown). The SWE documented this as a known limitation.

## Architecture Context

Events flow like this during a session:

1. `ClaudeCodeProcess.run()` yields raw JSON lines from the CLI
2. `ClaudeCodeParser.parse_line()` converts them into codehive event dicts (including `rate_limit.updated` and `usage.model_breakdown`)
3. `ClaudeCodeEngine.send_message()` yields those event dicts
4. Consumers (`send_message_endpoint`, `send_message_stream_endpoint`, `_run_engine_background`) iterate over the events but do NOT inspect or persist rate-limit/usage events -- they just collect or stream them

The persistence logic needs to live in the consumer layer (the session route handlers or a shared helper they call) because the engine itself does not have access to the database session.

### Key files

- `backend/codehive/engine/claude_code_parser.py` -- emits `rate_limit.updated` and `usage.model_breakdown` events (already done)
- `backend/codehive/engine/claude_code_engine.py` -- `send_message()` yields events (already done)
- `backend/codehive/api/routes/sessions.py` -- `send_message_endpoint`, `send_message_stream_endpoint` consume events
- `backend/codehive/api/routes/async_dispatch.py` -- `_run_engine_background` consumes events
- `backend/codehive/db/models.py` -- `RateLimitSnapshot`, `ModelUsageSnapshot` models (already done)
- `backend/codehive/api/routes/usage.py` -- `GET /api/usage/limits` reads from DB (already done)

## Scope

Add an event-processing helper that inspects each event yielded by the engine and, when the event type is `rate_limit.updated` or `usage.model_breakdown`, writes the corresponding snapshot row(s) to the database. Wire this helper into all three event consumers so that live sessions populate the usage limits data.

### In scope

- A shared async helper function (e.g. `persist_usage_event(db, session_id, event)`) that handles the two event types
- Calling this helper from `send_message_endpoint`, `send_message_stream_endpoint`, and `_run_engine_background`
- Unit tests for the helper
- Integration test: mock the engine to emit rate-limit and model-usage events, call the message endpoint, then verify `GET /api/usage/limits` returns the persisted data

### Out of scope

- Changing the parser or the engine
- Frontend changes (the UI already reads from `GET /api/usage/limits`)
- WebSocket broadcast of rate-limit events (separate concern)

## User Stories

### Story: Developer sends a message and rate-limit data appears in the usage dashboard

This is a backend-only feature. There is no new UI interaction -- the existing usage limits UI (built in #122) will start showing real data once this wiring is in place.

1. A session exists with `engine=claude_code`
2. The user sends a message via `POST /api/sessions/{id}/messages`
3. The Claude Code CLI stream includes a `rate_limit_event` JSON object
4. The parser emits a `rate_limit.updated` event
5. The event consumer persists a `RateLimitSnapshot` row to the database
6. `GET /api/usage/limits` now returns the rate-limit data with `utilization`, `resets_at`, `rate_limit_type`, etc.

### Story: Model usage breakdown appears after a session turn completes

1. A session exists with `engine=claude_code`
2. The user sends a message via `POST /api/sessions/{id}/messages`
3. The Claude Code CLI stream ends with a `result` JSON object containing `modelUsage`
4. The parser emits a `usage.model_breakdown` event
5. The event consumer persists one `ModelUsageSnapshot` row per model to the database
6. `GET /api/usage/limits` now returns the per-model breakdown with `input_tokens`, `output_tokens`, `cost_usd`, etc.

## Acceptance Criteria

- [ ] A helper function exists that takes a DB session, a codehive session ID, and an event dict, and persists `RateLimitSnapshot` for `rate_limit.updated` events and `ModelUsageSnapshot` row(s) for `usage.model_breakdown` events
- [ ] `send_message_endpoint` in `sessions.py` calls the helper for every event yielded by the engine
- [ ] `send_message_stream_endpoint` in `sessions.py` calls the helper for every event yielded by the engine
- [ ] `_run_engine_background` in `async_dispatch.py` calls the helper for every event yielded by the engine
- [ ] The helper correctly maps event fields to DB model columns:
  - `rate_limit.updated` -> `RateLimitSnapshot(session_id, rate_limit_type, utilization, resets_at, is_using_overage, surpassed_threshold)`
  - `usage.model_breakdown` -> one `ModelUsageSnapshot` per model in `event["models"]` with `(session_id, model, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, cost_usd, context_window)`
- [ ] `uv run pytest tests/ -v -k "usage_limits or persist_usage"` passes with 5+ new tests
- [ ] `uv run ruff check` is clean
- [ ] Existing tests in `test_usage_limits.py` continue to pass

## Test Scenarios

### Unit: persist_usage_event helper

- Call with a `rate_limit.updated` event, verify a `RateLimitSnapshot` row is written with correct fields
- Call with a `usage.model_breakdown` event containing 2 models, verify 2 `ModelUsageSnapshot` rows are written
- Call with an unrelated event type (e.g. `message.created`), verify no rows are written
- Call with a `rate_limit.updated` event without a session_id (None), verify it still persists (session_id is nullable)

### Integration: end-to-end via API

- Mock the engine to yield a `rate_limit.updated` event during `send_message`, then call `GET /api/usage/limits` and verify the rate-limit data appears in the response
- Mock the engine to yield a `usage.model_breakdown` event during `send_message`, then call `GET /api/usage/limits` and verify the model-usage data appears in the response
- Verify that the existing `GET /api/usage/limits` endpoint still works correctly when no usage events have been emitted (empty response)

## Dependencies

- #122 (usage limits and per-model breakdown) -- DONE

## Log

### [SWE] 2026-03-19 14:30
- Added `persist_usage_event(db, session_id, event)` async helper to `backend/codehive/core/usage.py`
  - Handles `rate_limit.updated` events by creating `RateLimitSnapshot` rows
  - Handles `usage.model_breakdown` events by creating one `ModelUsageSnapshot` row per model
  - No-op for all other event types
- Wired the helper into all 3 event consumers:
  - `send_message_endpoint` in `sessions.py` -- calls helper for each yielded event
  - `send_message_stream_endpoint` in `sessions.py` -- calls helper for each yielded event
  - `_run_engine_background` in `async_dispatch.py` -- calls helper for each yielded event
- Files modified:
  - `backend/codehive/core/usage.py` (added `persist_usage_event`)
  - `backend/codehive/api/routes/sessions.py` (import + 2 call sites)
  - `backend/codehive/api/routes/async_dispatch.py` (import + 1 call site)
- Files created:
  - `backend/tests/test_persist_usage_event.py` (8 new tests)
- Tests added: 8 tests
  - 5 unit tests for the helper (rate_limit event, model_breakdown with 2 models, unrelated event, None session_id, empty models list)
  - 3 integration tests (mock engine yields rate_limit -> verify via GET /api/usage/limits, mock engine yields model_breakdown -> verify via GET /api/usage/limits, empty response when no events)
- Build results: 1957 pass, 2 fail (pre-existing in test_cli.py, unrelated to this change), ruff clean, tsc clean
- Known limitations: none

### [QA] 2026-03-19 15:00
- Tests (issue-specific): 8 passed, 0 failed (`uv run pytest tests/test_persist_usage_event.py -v`)
- Tests (full backend): 1957 passed, 2 failed (pre-existing in test_cli.py, unrelated), 3 skipped
- Ruff check: clean
- Ruff format: clean (259 files already formatted)
- Acceptance criteria:
  - [x] Helper function `persist_usage_event(db, session_id, event)` exists in `backend/codehive/core/usage.py` -- PASS
  - [x] `send_message_endpoint` in `sessions.py` calls helper for every event -- PASS (line 471)
  - [x] `send_message_stream_endpoint` in `sessions.py` calls helper for every event -- PASS (line 525)
  - [x] `_run_engine_background` in `async_dispatch.py` calls helper for every event -- PASS (line 67)
  - [x] Helper correctly maps `rate_limit.updated` fields to `RateLimitSnapshot` columns -- PASS (verified by unit test `test_rate_limit_event_creates_snapshot` checking all fields)
  - [x] Helper correctly maps `usage.model_breakdown` to one `ModelUsageSnapshot` per model -- PASS (verified by unit test `test_model_breakdown_creates_snapshots` with 2 models)
  - [x] `uv run pytest tests/ -v -k "usage_limits or persist_usage"` passes with 5+ new tests -- PASS (8 new tests all pass)
  - [x] `uv run ruff check` is clean -- PASS
  - [x] Existing tests in `test_usage_limits.py` continue to pass -- PASS (included in full suite run)
- VERDICT: PASS
