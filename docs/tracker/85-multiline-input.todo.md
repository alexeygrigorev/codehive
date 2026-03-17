# Issue #85: Multiline input in codehive code TUI

## Problem

The `codehive code` TUI uses a single-line `Input` widget. Users can't paste or type multiline prompts. Need to support multiline input with Enter to submit and Shift+Enter (or similar) for newlines.

## Requirements

- [ ] Replace `Input` with `TextArea` (or similar) for the chat input
- [ ] Enter submits the message, Shift+Enter inserts a newline
- [ ] Input area should grow up to ~5 lines then scroll internally
- [ ] Paste should work with multiline content (Ctrl+V)
- [ ] Keep the input compact (1 line) when empty, expand as content grows
