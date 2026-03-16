# 81a: Include Spike Ratio in Error Rate Spike Notification

## Description

The `error.rate_spike` event published by `ErrorRateMonitor` does not include the spike ratio (current_window_count / previous_window_count). The Telegram notification formatter therefore cannot display the ratio, which was specified in issue #81 AC 14: "a message containing the error count and spike ratio."

Currently the notification shows `errors_per_minute` instead of the ratio. Both values are useful -- this issue adds the ratio to the event data and notification message.

## Scope

### Modified Files
- `backend/codehive/core/error_tracking.py` -- Pass `spike_ratio` and `previous_window_errors` into the `error.rate_spike` event data from `ErrorRateMonitor._check()`
- `backend/codehive/clients/telegram/formatters.py` -- Include spike ratio in `format_error_rate_spike_notification()` output (e.g., "3.5x normal")
- `backend/tests/test_error_tracking.py` -- Update Telegram formatter test to verify ratio is present; add test that event data includes ratio

## Dependencies

- Depends on: #81 (error tracking) -- DONE

## Acceptance Criteria

- [ ] `error.rate_spike` event data includes `spike_ratio` field (float, e.g. 3.5)
- [ ] `format_error_rate_spike_notification()` output contains the spike ratio (e.g., "3.5x normal")
- [ ] Existing tests updated and passing

## Log

### [SWE] 2026-03-16 14:00
- Added `spike_ratio` and `previous_window_errors` to `error.rate_spike` event data in `ErrorRateMonitor._check()`
- Computes ratio as `window_errors / previous_window_errors` (or `float(window_errors)` when previous is 0)
- Updated `format_error_rate_spike_notification()` to show "Spike ratio: Xx normal" when ratio is present
- Updated existing formatter test to include `spike_ratio: 3.5` and verify "3.5x normal" appears
- Added new test `test_format_error_rate_spike_without_ratio` for backward compatibility
- Added new test `test_spike_event_includes_ratio` verifying event payload contains `spike_ratio` (3.5) and `previous_window_errors` (2)
- Build: 31 tests pass, 0 fail, ruff clean
- Files modified: `backend/codehive/core/error_tracking.py`, `backend/codehive/clients/telegram/formatters.py`, `backend/tests/test_error_tracking.py`

### [QA] 2026-03-16 14:30
- Tests: 31 passed, 0 failed
- Ruff: clean (check and format)
- Acceptance criteria:
  - AC1 (spike_ratio in event data): PASS -- field included in publish call, verified by test_spike_event_includes_ratio
  - AC2 (formatter output contains ratio e.g. "3.5x normal"): PASS -- format_error_rate_spike_notification outputs "Spike ratio: 3.5x normal", verified by test
  - AC3 (existing tests updated and passing): PASS -- 31/31 pass, 2 new tests added (backward compat without ratio, event payload includes ratio)
- VERDICT: PASS

### [PM] 2026-03-16 15:00
- Reviewed diff: 3 files changed (error_tracking.py, formatters.py, test_error_tracking.py)
- Results verified: real test results present (31/31 tests pass per SWE and QA logs, 2 new tests added)
- Acceptance criteria:
  - AC1 (spike_ratio field in event data): MET -- error_tracking.py computes spike_ratio = window_errors / previous_window_errors (rounded to 2 decimal places), falls back to float(window_errors) when previous is 0. Field included in publish() data dict. Verified by test_spike_event_includes_ratio asserting spike_ratio == 3.5 and previous_window_errors == 2.
  - AC2 (formatter output contains spike ratio e.g. "3.5x normal"): MET -- formatters.py appends "Spike ratio: {spike_ratio}x normal" when spike_ratio is present. Verified by test asserting "3.5x normal" in output.
  - AC3 (existing tests updated and passing): MET -- existing formatter test updated to include spike_ratio: 3.5 and assert "3.5x normal". Two new tests added: backward compatibility without ratio, and event payload verification. 31/31 pass.
- Code quality: Clean implementation. Backward-compatible (formatter handles missing spike_ratio gracefully). The previous-window query is a reasonable approach -- queries the same time window length immediately preceding the current window.
- Tests are meaningful: test_spike_event_includes_ratio sets up 2 errors in previous window and 7 in current, verifies ratio is 3.5. test_format_error_rate_spike_without_ratio verifies backward compat when spike_ratio is absent. Both are substantive, not smoke tests.
- Follow-up issues created: none needed
- VERDICT: ACCEPT
