# Issue #128: Wire engine to persist rate_limit and model_usage events to DB

## Problem

Issue #122 added parsing of `rate_limit_event` and `modelUsage` from the Claude Code stream, plus DB models, API endpoint, and frontend UI. However, the engine's event handler does not yet subscribe to the `rate_limit.updated` and `usage.model_breakdown` events to persist them to the database during live sessions.

Without this wiring, the plan limits data will never appear in the UI during normal operation -- it can only be inserted manually or via tests.

## Origin

Descoped from #122 (usage limits and per-model breakdown). The SWE documented this as a known limitation.

## Scope

- Subscribe to `rate_limit.updated` events in the engine event handler and write `RateLimitSnapshot` rows to the DB
- Subscribe to `usage.model_breakdown` events in the engine event handler and write `ModelUsageSnapshot` rows to the DB
- Verify with an integration test that running a Claude Code session with rate limit data in the stream results in data appearing at `GET /api/usage/limits`

## Dependencies

- #122 (usage limits and per-model breakdown) -- DONE
