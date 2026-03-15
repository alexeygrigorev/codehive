# 30a: Dashboard-to-Rescue Keybinding

## Description
Wire a keybinding (e.g., `!` or `r`) on the main TUI dashboard to push the RescueScreen onto the screen stack, and ensure `escape` from the rescue screen pops back to the dashboard.

This was part of the integration test scenarios in issue #30 but was descoped from the initial implementation.

## Scope
- `backend/codehive/clients/terminal/screens/dashboard.py` -- Add keybinding to push RescueScreen
- `backend/tests/test_rescue.py` or new test file -- Integration test for dashboard-to-rescue navigation

## Dependencies
- Depends on: #30 (TUI rescue mode) -- DONE
- Depends on: #27 (TUI app shell) -- DONE

## Acceptance Criteria

- [ ] A keybinding on the dashboard pushes the RescueScreen onto the screen stack
- [ ] Pressing `escape` from rescue screen pops back to the dashboard
- [ ] Test verifies the navigation round-trip (dashboard -> rescue -> escape -> dashboard)
