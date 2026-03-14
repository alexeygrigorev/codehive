# 16: Web Session Chat Panel

## Description
Implement the core session view chat panel with streaming message display. This is the main interaction surface where users communicate with the agent, see responses streamed in real-time, and view tool call results inline.

## Scope
- `web/src/pages/SessionPage.tsx` -- Session view layout (chat + sidebar)
- `web/src/components/ChatPanel.tsx` -- Chat message list with streaming support
- `web/src/components/ChatInput.tsx` -- Message input with send button
- `web/src/components/MessageBubble.tsx` -- Individual message rendering (user, assistant, system, tool)
- `web/src/components/ToolCallResult.tsx` -- Inline rendering of tool call results
- `web/src/api/messages.ts` -- API hooks for sending messages and fetching history

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #05 (session CRUD API)
- Depends on: #09 (engine adapter for sending messages)
- Depends on: #18 (WebSocket client for streaming)
