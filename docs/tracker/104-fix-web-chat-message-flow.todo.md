# Issue #104: Fix web chat — messages sent but responses not displayed

## Problem

When sending a message in the web chat, the user's message appears but the assistant's response never shows up. The backend works correctly — `POST /api/sessions/{id}/messages` returns all events (deltas + final message). But the frontend doesn't render them.

## Root Cause Analysis

Two issues in the event flow:

1. **`sendMessage()` response is discarded.** `ChatPanel.handleSend` calls `await sendMessage(sessionId, content)` which returns the response events, but the return value is never used. The events are thrown away.

2. **Event format mismatch.** The `POST /messages` endpoint returns flat events like `{type, role, content, session_id}`. But `ChatPanel` reads `event.data.role` and `event.data.content` — the `SessionEvent` shape expects `{id, type, data: {role, content}, session_id, created_at}`. The flat events from the HTTP response don't have the `data` wrapper.

The WebSocket path (which does have proper `SessionEvent` shape) should be receiving these events too via the EventBus, but the synchronous nature of the `POST /messages` endpoint means the request blocks until the engine finishes — by which time the WebSocket events may have already been received and deduplicated, or missed entirely due to timing.

## Fix Options

**Option A (recommended):** After `sendMessage()` returns, normalize the response events using `normalizeEvent()` (already exists in `websocket.ts`) and inject them into the WebSocket context's live events. This ensures they show up even if the WebSocket missed them.

**Option B:** Change the `POST /messages` endpoint to return events in `SessionEvent` shape (with `data` wrapper, `id`, `created_at`). This fixes the format but doesn't fix the WebSocket timing issue.

**Option C:** Don't use the return value at all — rely entirely on WebSocket for live events. But this requires the WebSocket to reliably deliver all events during the synchronous POST, which has timing issues.

## Requirements

- [ ] After sending a message, the assistant response appears in the chat
- [ ] Streaming deltas show token-by-token as they arrive
- [ ] Tool calls appear inline
- [ ] No duplicate messages (deduplication between HTTP response events and WebSocket events)
- [ ] Works on page refresh (history loading already works from #97)

## Files involved

- `web/src/components/ChatPanel.tsx` — handleSend discards return value
- `web/src/api/messages.ts` — sendMessage returns events
- `web/src/api/websocket.ts` — normalizeEvent() exists
- `web/src/context/WebSocketContext.tsx` — manages event state
- `backend/codehive/api/routes/sessions.py` — POST /messages endpoint returns flat events
