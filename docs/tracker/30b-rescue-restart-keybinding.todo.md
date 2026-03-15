# 30b: Rescue Mode - Restart Keybinding

## Description
Add the `x` keybinding to the rescue screen that restarts a selected session (pause then resume). This was described in the Behavior section of issue #30 but was not included in the acceptance criteria.

## Scope
- `backend/codehive/clients/terminal/screens/rescue.py` -- Add `x` keybinding for restart (pause + resume)
- `backend/tests/test_rescue.py` -- Test that pressing `x` calls pause then resume on the API

## Dependencies
- Depends on: #30 (TUI rescue mode) -- DONE

## Acceptance Criteria

- [ ] Pressing `x` on a selected session pauses and then resumes it
- [ ] Test verifies `x` keybinding calls both pause and resume API methods in sequence
- [ ] Error handling: if pause fails, do not attempt resume; show error message
