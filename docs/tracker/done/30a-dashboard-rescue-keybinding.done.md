# 30a: Dashboard-to-Rescue Keybinding

## Description
Wire a keybinding on the main TUI dashboard to push the RescueScreen onto the screen stack, and ensure `escape` from the rescue screen pops back to the dashboard.

This was part of the integration test scenarios in issue #30 but was descoped from the initial implementation.

## Scope
- `backend/codehive/clients/terminal/screens/dashboard.py` -- Add a new binding (use `!` key, since `r` could collide with future bindings) and an `action_show_rescue` method that calls `self.app.push_screen(RescueScreen())`
- `backend/tests/test_rescue.py` (or a new test file) -- Add integration tests for dashboard-to-rescue navigation round-trip

No changes needed to `rescue.py` -- it already has `("escape", "go_back", "Back")` which pops the screen stack.

## Dependencies
- Depends on: #30 (TUI rescue mode) -- DONE
- Depends on: #27 (TUI app shell) -- DONE

## Acceptance Criteria

- [ ] DashboardScreen.BINDINGS includes a binding for the `!` key labeled "Rescue"
- [ ] Pressing `!` on the dashboard pushes RescueScreen onto the screen stack (the active screen becomes RescueScreen)
- [ ] Pressing `escape` on the RescueScreen pops back to DashboardScreen (existing behavior, just needs verification in context)
- [ ] The Footer widget on the dashboard shows the "!" / "Rescue" binding
- [ ] `uv run pytest backend/tests/test_rescue.py -v` passes with all existing tests plus the new navigation tests (at minimum 2 new tests)
- [ ] No regressions: `uv run pytest backend/tests/ -v` passes

## Test Scenarios

### Unit: Dashboard keybinding registration
- Verify that DashboardScreen.BINDINGS contains a `!` -> `action_show_rescue` entry

### Integration: Dashboard-to-Rescue navigation (using CodehiveApp with mocked API)
- Start CodehiveApp, verify DashboardScreen is active, press `!`, verify RescueScreen is now the active screen
- Start CodehiveApp, press `!` to push RescueScreen, then press `escape`, verify DashboardScreen is active again (round-trip)

### Regression: Existing rescue tests still pass
- All tests in `test_rescue.py` continue to pass unchanged (RescueApp standalone path is unaffected)

## Implementation Notes
- Follow the existing pattern in `dashboard.py` where `action_show_projects` uses a deferred import and calls `self.app.push_screen(...)`.
- The `RescueScreen` import should be deferred (inside the action method) to avoid circular imports, matching the pattern used for `ProjectDetailScreen` and `ProjectListScreen`.
- The mocked `api_client` on CodehiveApp needs the rescue-related methods (`get_system_health`, `list_projects`, `list_sessions`, `list_questions`) since RescueScreen calls them on mount.

## Log

### [SWE] 2026-03-15 00:00
- Added `exclamation_mark` -> `show_rescue` binding to DashboardScreen.BINDINGS
- Added `action_show_rescue` method with deferred import of RescueScreen, following existing pattern from `action_show_projects`
- Added 3 new tests to test_rescue.py:
  - `test_dashboard_bindings_include_rescue`: unit test verifying BINDINGS registration
  - `test_press_exclamation_pushes_rescue_screen`: integration test pressing ! on dashboard
  - `test_rescue_escape_returns_to_dashboard`: integration round-trip test (! then escape)
- Added `_build_codehive_app_with_rescue_api` helper that mocks all rescue-required API methods
- Files modified: backend/codehive/clients/terminal/screens/dashboard.py, backend/tests/test_rescue.py
- Tests added: 3 new tests
- Build results: 53 tests pass (test_tui.py + test_rescue.py), 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-15 14:00
- Tests: 1030 passed, 0 failed (full suite); 53 passed in test_tui.py + test_rescue.py
- Ruff: clean (check + format)
- Acceptance criteria:
  - DashboardScreen.BINDINGS includes `!` key labeled "Rescue": PASS
  - Pressing `!` on the dashboard pushes RescueScreen: PASS
  - Pressing `escape` on RescueScreen pops back to DashboardScreen: PASS
  - Footer widget shows the "!" / "Rescue" binding: PASS
  - pytest passes with new navigation tests (3 new, minimum was 2): PASS
  - No regressions (1030 tests pass): PASS
- Code quality: deferred import pattern followed, type hints present, no hardcoded values
- VERDICT: PASS

### [PM] 2026-03-15 14:30
- Reviewed diff: 4 files changed (dashboard.py, rescue.py, api_client.py, test_rescue.py) -- 30a touches dashboard.py and test_rescue.py
- Results verified: real data present -- QA ran 1030 tests, 53 in TUI+rescue subset, all pass
- Acceptance criteria: all 6 met
  - [x] DashboardScreen.BINDINGS includes `!` key labeled "Rescue" -- confirmed in dashboard.py line 45
  - [x] Pressing `!` pushes RescueScreen -- confirmed by integration test and code at line 154-157
  - [x] Pressing `escape` on RescueScreen pops back to DashboardScreen -- confirmed by round-trip test
  - [x] Footer widget shows the "!" / "Rescue" binding -- Textual Footer auto-renders BINDINGS; QA confirmed
  - [x] pytest passes with 3 new tests (minimum was 2) -- confirmed
  - [x] No regressions: 1030 tests pass -- confirmed
- Tests are meaningful: class-level binding check, real Textual pilot press/screen-type assertions, full round-trip
- Code is clean: deferred import pattern matches existing `action_show_projects`, no circular import risk
- Follow-up issues created: none
- VERDICT: ACCEPT
