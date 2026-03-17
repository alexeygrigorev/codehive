# Issue #83: Streaming support and terminal UX improvements

## Problem

The `codehive code` TUI and the backend engine currently batch responses — the user sees nothing until the full agent turn completes. The TUI also lacks:
- Footer with hotkey hints (Ctrl+Q to quit, etc.)
- Markdown rendering for assistant responses
- Streaming token-by-token output

Streaming should be implemented at the engine level so it benefits all clients (web, mobile, TUI, Telegram), not just the terminal.

## Requirements

### Streaming (engine-level)
- [ ] NativeEngine: use `client.messages.stream()` instead of `client.messages.create()` to get token-by-token output
- [ ] Yield incremental `message.delta` events (partial text) alongside the existing `message.created` (final text)
- [ ] WebSocket endpoint should forward `message.delta` events to connected clients
- [ ] ClaudeCodeEngine: already streams via stdout — parse incremental `content_block_delta` events and yield them

### Terminal UX (`codehive code`)
- [ ] Footer with hotkey bindings: Ctrl+Q quit, Ctrl+L clear, Ctrl+N new session
- [ ] Render assistant responses as Markdown (use `textual.widgets.Markdown` or `rich.markdown.Markdown`)
- [ ] Stream tokens into the chat panel as they arrive (append to current message bubble)
- [ ] Show a spinner/progress indicator while agent is thinking
- [ ] Show elapsed time for agent turns

### Web client
- [ ] Update WebSocket handler to process `message.delta` events
- [ ] Stream tokens into the chat UI as they arrive

## Notes

- Textual has a built-in `Markdown` widget that renders rich markdown
- The Anthropic SDK supports `async with client.messages.stream(...)` which yields `text` events
- Keep `message.created` as the final complete message event for backwards compatibility
