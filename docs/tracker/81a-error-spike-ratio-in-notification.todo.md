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
