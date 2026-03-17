# Issue #85: Multiline input in codehive code TUI

## Problem

The `codehive code` TUI uses a single-line `Input` widget. Users cannot paste or type multiline prompts. Need to support multiline input with Enter to submit and Shift+Enter for newlines.

## Scope

Replace the `Input` widget in `backend/codehive/clients/terminal/code_app.py` with a `TextArea`-based input that supports multiline editing. The change is isolated to this one file (and its tests). No backend or API changes needed.

### Key files
- `backend/codehive/clients/terminal/code_app.py` -- the `CodeApp` class
- `backend/tests/test_code_app.py` -- new test file for CodeApp multiline input

## Requirements

- [ ] Replace `Input` widget with `TextArea` (from `textual.widgets`) for the chat input (`#code-input`)
- [ ] Enter key submits the message (calls the same logic as current `on_input_submitted`)
- [ ] Shift+Enter inserts a newline in the text area
- [ ] Input area starts at 1-3 lines tall when empty, grows as content is added, caps at ~5 lines then scrolls internally
- [ ] Multiline paste works (Ctrl+V pastes multiline content into the TextArea)
- [ ] After submission, the input area clears and returns to its compact size
- [ ] Existing functionality preserved: `/quit`, `/exit` commands, disabled state while agent is thinking, focus management

## Implementation Notes

- Textual's `TextArea` widget supports multiline out of the box. Key binding customization is needed to override Enter (which normally inserts a newline in TextArea) to submit instead.
- Use `TextArea.register_bindings = False` or bind overrides to remap Enter to submit and Shift+Enter to newline.
- The height should be controlled via CSS with `min-height` and `max-height`, or by dynamically adjusting `styles.height` based on line count.
- The current `action_paste` method uses clipboard tools (xclip/xsel/wl-paste). TextArea may handle paste natively via Textual's built-in paste support -- verify and simplify if possible.
- Update all references to `Input` in CodeApp: `query_one("#code-input", Input)` calls, `on_input_submitted` handler, focus management, disabled state toggling.

## Dependencies

- None. The `codehive code` TUI and its `CodeApp` class already exist and work with single-line input.

## Acceptance Criteria

- [ ] `cd backend && uv run pytest tests/test_code_app.py -v` passes with 4+ tests
- [ ] `TextArea` widget is used instead of `Input` for `#code-input` in `CodeApp.compose()`
- [ ] Pressing Enter in the input area submits the message (appends user bubble, triggers agent)
- [ ] Pressing Shift+Enter in the input area inserts a newline without submitting
- [ ] Input area is compact (1-3 lines) when empty; grows up to ~5 lines as content is typed; scrolls internally beyond that
- [ ] After submission, input area clears and shrinks back to compact size
- [ ] Pasting multiline text into the input area preserves all lines
- [ ] `/quit` and `/exit` still work as typed commands
- [ ] Input is disabled (non-editable or visually indicated) while the agent is processing
- [ ] `cd backend && uv run ruff check codehive/clients/terminal/code_app.py` is clean

## Test Scenarios

### Unit: Widget replacement
- `CodeApp` composes with a `TextArea` widget with id `code-input` (not `Input`)
- The TextArea is present and focusable on mount

### Unit: Enter submits
- Type text into the TextArea, press Enter -- the message appears as a user chat bubble
- The TextArea is cleared after submission
- Empty input (whitespace only) does not submit

### Unit: Shift+Enter inserts newline
- Press Shift+Enter in the TextArea -- a newline character is inserted, no submission occurs
- The TextArea content contains the newline

### Unit: Input disabled during processing
- While `_busy` is True, the input should be disabled or reject input
- After processing completes, input is re-enabled and focused

### Integration: Multiline message flow
- Type a multiline message (using Shift+Enter), then press Enter to submit -- the full multiline text appears in the user bubble

## Log

### [QA] 2026-03-17 10:00
- Tests: 10 passed, 0 failed (in tests/test_code_app.py)
- Full TUI test suite: 58 passed, 0 failed (test_code_app + test_tui + test_tui_session)
- Ruff check: clean
- Ruff format: clean (fixed formatting issues in code_app.py and native.py during review)
- Acceptance criteria:
  1. `cd backend && uv run pytest tests/test_code_app.py -v` passes with 4+ tests: PASS (10 tests)
  2. `TextArea` widget used instead of `Input` for `#code-input`: PASS
  3. Enter submits message: PASS (tested: text appears as user bubble, input clears)
  4. Shift+Enter inserts newline without submitting: PASS (tested: newline present in text)
  5. Input area compact (3 lines) when empty, grows up to 5 lines: PASS (_MIN_HEIGHT=3, _MAX_HEIGHT=5, _resize_to_content clamps)
  6. After submission, input clears and shrinks: PASS (clear_input resets height to _MIN_HEIGHT)
  7. Pasting multiline text preserves lines: PASS (action_paste calls inp.insert + _resize_to_content)
  8. `/quit` and `/exit` still work: PASS (tested both commands)
  9. Input disabled while agent processing: PASS (tested: disabled+read_only set, wait message shown)
  10. `ruff check codehive/clients/terminal/code_app.py` clean: PASS
- VERDICT: PASS

### [PM] 2026-03-17 11:15
- Reviewed diff: 2 files changed (code_app.py +173 lines, test_code_app.py new 219 lines)
- Results verified: real data present -- 10/10 tests pass, ruff clean
- Acceptance criteria: all 10 met
  1. 10 tests pass (threshold 4+): PASS
  2. TextArea (_ChatInput) used for #code-input: PASS
  3. Enter submits via _on_key intercept + Submitted message: PASS
  4. Shift+Enter inserts newline via _replace_via_keyboard: PASS
  5. Compact 3 lines, grows to 5, scrolls internally: PASS
  6. clear_input() resets text and height after submission: PASS
  7. action_paste uses inp.insert + _resize_to_content: PASS
  8. /quit and /exit tested and working: PASS
  9. disabled + read_only set while busy: PASS
  10. ruff check clean: PASS
- Note: diff includes approval_callback code from issue #86; no conflict, isolated concern
- Follow-up issues created: none needed
- VERDICT: ACCEPT
