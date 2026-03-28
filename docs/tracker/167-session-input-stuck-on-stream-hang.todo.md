# Issue #167: Session input gets permanently stuck when SSE stream hangs

## Problem

When a user sends a message in a session and the backend stops responding mid-stream (crash, timeout, network issue), the chat input becomes permanently disabled with no way to recover except refreshing the page.

**User report:** Session at `/sessions/862e7345-4be3-4914-92e4-82aeee8b3378` is "not responding."

## Root Cause

In `web/src/components/ChatPanel.tsx`, the `handleSend` function (line 189-239):

1. Sets `sending = true` (line 191), which disables the ChatInput
2. Calls `await sendMessage(sessionId, content, onEvent)` (line 206)
3. Sets `sending = false` in `finally` block (line 234)

In `web/src/api/messages.ts`, `sendMessage` reads from an SSE stream in a `while(true)` loop (line 42-73):
```typescript
while (true) {
  const { done, value } = await reader.read();  // <-- hangs forever if backend stops
  if (done) break;
  ...
}
```

If the backend crashes or the connection drops without a clean close, `reader.read()` never resolves. The promise never settles, so `finally` never runs, and `sending` stays `true` forever — **permanently disabling the input**.

Additionally:
- There is no timeout on the SSE stream read
- There is no AbortController to cancel the fetch
- There is no "connection lost" indicator in the UI
- The `sending` state has no timeout/watchdog to auto-reset

## Affected Files

- `web/src/api/messages.ts` — SSE stream reader with no timeout/abort
- `web/src/components/ChatPanel.tsx` — `sending` state with no recovery mechanism
- `web/src/components/ChatInput.tsx` — disabled prop reflects stuck state

## Expected Behavior

- If the SSE stream doesn't receive data for N seconds, abort and show an error
- The input should re-enable after a failed send attempt
- A "reconnect" or "retry" option should be available
- The user should see a clear error message, not a silently frozen input
