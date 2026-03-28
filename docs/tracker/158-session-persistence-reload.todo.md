# 158 — Session persistence: messages survive page reload

## Problem
When the user reloads the page during an active session, they lose all messages. The agent process continues in the backend but the frontend has no way to recover the conversation state. The user sees a blank chat.

## Root cause
Messages from the current SSE stream are held in React state only. When the page reloads, the state is lost. The backend streams events but doesn't persist individual messages/tool calls in a way the frontend can re-fetch.

## Expected behavior
1. **Backend persists all messages**: every user message, assistant message, tool call, and tool result is saved to the database as it happens
2. **Frontend loads history on mount**: when the session page loads, it fetches all persisted messages and renders them
3. **SSE stream resumes**: new events from the ongoing agent process appear after the history
4. **No duplicates**: messages from history and SSE are deduplicated by ID

## Acceptance criteria
- [ ] Backend persists each message (user, assistant, tool_use, tool_result) to the messages table during streaming
- [ ] GET /api/sessions/{id}/messages returns all persisted messages in order
- [ ] Frontend fetches message history on session page mount
- [ ] History renders before SSE events (no flash of empty state)
- [ ] SSE events that already exist in history are deduplicated
- [ ] Reloading the page during an active agent shows all previous messages + continues streaming
- [ ] Tool calls in history render with the same UI as live tool calls (#157)
- [ ] Works for completed sessions too (history is the full conversation)
