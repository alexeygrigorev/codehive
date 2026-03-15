# 30b: Rescue Mode - Restart Keybinding

## Description
Add the `x` keybinding to the rescue screen that restarts a selected session (pause then resume). This was described in the Behavior section of issue #30 but was not included in the acceptance criteria.

## Scope
- `backend/codehive/clients/terminal/api_client.py` -- Add `resume_session` method (currently missing; the API route `POST /api/sessions/{id}/resume` already exists)
- `backend/codehive/clients/terminal/screens/rescue.py` -- Add `x` keybinding bound to `action_restart_session`, which calls `_do_restart` (pause then resume in a `@work(thread=True)` method)
- `backend/tests/test_rescue.py` -- Tests for the new keybinding and restart logic

## Dependencies
- Depends on: #30 (TUI rescue mode) -- DONE

## Acceptance Criteria

- [ ] `APIClient` has a `resume_session(session_id)` method that calls `POST /api/sessions/{session_id}/resume`
- [ ] `RescueScreen.BINDINGS` includes `("x", "restart_session", "Restart")`
- [ ] Pressing `x` with a session selected calls `api.pause_session(session_id)` followed by `api.resume_session(session_id)` in sequence
- [ ] If pause fails (raises an exception), resume is NOT called and the error widget displays a message starting with "Restart failed:"
- [ ] If pause succeeds but resume fails, the error widget displays a message (session remains paused -- acceptable; the user can manually resume)
- [ ] After a successful restart, `_load_data` is called to refresh the table
- [ ] Pressing `x` with no session selected (empty table or table hidden) is a no-op -- no crash, no API call
- [ ] `uv run pytest backend/tests/test_rescue.py -v` passes with all existing tests plus the new ones

## Test Scenarios

### Unit: APIClient.resume_session
- `resume_session("sess-123")` calls `POST /api/sessions/sess-123/resume` with `json=None` and returns the response JSON

### Unit: RescueScreen restart action
- Press `x` with a session selected -- verify `pause_session` called with the correct session ID, then `resume_session` called with the same session ID, in that order
- Press `x` when pause raises an exception -- verify `resume_session` is NOT called and error widget is visible with an appropriate message
- Press `x` when pause succeeds but resume raises -- verify error widget is visible
- Press `x` with no sessions in the table (empty API) -- verify no API calls made and no crash

### Regression
- All existing test classes in `test_rescue.py` continue to pass (no regressions from adding the new binding)

## Log

### [SWE] 2026-03-15 12:00
- Added `resume_session(session_id)` method to `APIClient` that calls `POST /api/sessions/{session_id}/resume`
- Added `("x", "restart_session", "Restart")` binding to `RescueScreen.BINDINGS`
- Added `action_restart_session` and `_do_restart` methods to `RescueScreen`: pause then resume in a `@work(thread=True)` method, with error handling for both steps
- If pause fails, resume is not called and error widget shows "Restart failed: ..."
- If resume fails, error widget shows "Restart failed: ..."
- After successful restart, `_load_data` is called to refresh the table
- Pressing `x` with no session selected is a no-op (guarded by `_get_selected_session_id()` returning None)
- Files modified: `backend/codehive/clients/terminal/api_client.py`, `backend/codehive/clients/terminal/screens/rescue.py`, `backend/tests/test_rescue.py`
- Tests added: 5 new tests (1 APIClient unit test for resume_session, 4 RescueScreen restart action tests)
- Build results: 33 tests pass, 0 fail, ruff clean

### [QA] 2026-03-15 14:00
- Tests: 1030 passed, 0 failed (full suite); 33 passed in test_rescue.py
- Ruff: clean (check + format)
- Acceptance criteria:
  - APIClient has resume_session(session_id) calling POST /api/sessions/{session_id}/resume: PASS
  - RescueScreen.BINDINGS includes ("x", "restart_session", "Restart"): PASS
  - Pressing x calls pause then resume in sequence: PASS
  - If pause fails, resume NOT called, error displays "Restart failed:": PASS
  - If pause succeeds but resume fails, error widget displays message: PASS
  - After successful restart, _load_data is called to refresh: PASS
  - Pressing x with no session selected is no-op: PASS
  - pytest passes with all existing + new tests: PASS
- Code quality: @work(thread=True) pattern followed, proper error handling, type hints present
- VERDICT: PASS

### [PM] 2026-03-15 14:30
- Reviewed diff: 3 files changed for 30b (api_client.py, rescue.py, test_rescue.py); 228 insertions total across both issues
- Results verified: real data present -- QA ran 1030 tests, 33 in test_rescue.py, all pass, ruff clean
- Acceptance criteria: all 8 met
  - [x] APIClient has resume_session(session_id) calling POST /api/sessions/{session_id}/resume -- confirmed in api_client.py lines 93-95
  - [x] RescueScreen.BINDINGS includes ("x", "restart_session", "Restart") -- confirmed in rescue.py line 58
  - [x] Pressing x calls pause then resume in sequence -- confirmed by test with call_order tracking
  - [x] If pause fails, resume NOT called, error displays "Restart failed:" -- confirmed by test asserting not_called + startswith check
  - [x] If pause succeeds but resume fails, error widget visible -- confirmed by test
  - [x] After successful restart, _load_data called to refresh -- confirmed in rescue.py line 299
  - [x] Pressing x with no session selected is no-op -- confirmed by test with empty API
  - [x] pytest passes with all existing + 5 new tests -- confirmed
- Tests are meaningful: happy path with call ordering, both failure modes (pause fail, resume fail), empty-table edge case, APIClient unit test
- Code is clean: follows existing @work(thread=True) pattern, proper try/except with call_from_thread for error display, guard via _get_selected_session_id
- Follow-up issues created: none
- VERDICT: ACCEPT
