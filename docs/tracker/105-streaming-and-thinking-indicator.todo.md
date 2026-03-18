# Issue #105: Streaming responses and thinking indicator in web chat

## Problem

Currently the web chat shows the assistant's response only after the full response is received — no streaming, no indication that anything is happening. The user sends a message and stares at a blank screen until the response appears all at once.

Two issues:
1. **No streaming** — Response appears all at once instead of token-by-token
2. **No thinking indicator** — Between sending a message and receiving the first token, there's no visual feedback that the agent is working

## Requirements

- [ ] After sending a message, immediately show a "thinking" indicator (typing bubble, pulsing dots, or similar) to confirm the request was received and the agent is processing
- [ ] Stream response tokens as they arrive — show them token-by-token in the assistant message bubble
- [ ] The thinking indicator disappears when the first token arrives and transitions into the streaming response
- [ ] Streaming should feel responsive — tokens appear as soon as they're available, not batched
- [ ] Session status should update to "running" or "thinking" while the agent is working
- [ ] Works with the native engine (which already supports streaming via `message.delta` events)

## UX Flow

1. User types message and presses Enter/Send
2. User message appears in chat
3. **Immediately**: A thinking indicator appears below the user message (e.g., three pulsing dots in an assistant-colored bubble, or "Agent is thinking..." text)
4. **When first token arrives**: Thinking indicator is replaced by the actual streaming text
5. **As tokens stream**: Text appears token-by-token in the assistant bubble
6. **When complete**: Final message is displayed, session status returns to "idle"

## Technical Notes

- The backend already streams `message.delta` events with partial content
- `ChatPanel.tsx` already has delta handling logic (`handleDelta`) that accumulates into a buffer
- The issue may be that deltas arrive via WebSocket but aren't being processed, or that the HTTP response path (from `sendMessage`) doesn't stream
- The thinking indicator is purely frontend — show it immediately after `sendMessage()` is called, hide it on first delta or response event
- Consider using SSE or WebSocket for real-time streaming instead of waiting for the full HTTP response

## Files likely involved

- `web/src/components/ChatPanel.tsx` — delta handling, thinking indicator state
- `web/src/components/MessageBubble.tsx` — streaming text display
- `web/src/context/WebSocketContext.tsx` — event flow
- `web/src/api/messages.ts` — sendMessage implementation
- New component: `ThinkingIndicator.tsx` or similar
