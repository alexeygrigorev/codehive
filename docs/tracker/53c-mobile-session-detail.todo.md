# 53c: Mobile Session Detail Screen

## Description
Build the session detail screen with a chat view showing message history, ability to send messages, and live status updates via WebSocket.

## Implementation Plan

### 1. Session detail screen
- `mobile/src/screens/SessionDetailScreen.tsx` -- chat view + status header
- Header: session name, mode indicator, status badge
- Chat area: FlatList (inverted) of messages, each with role icon (user/assistant/system/tool)
- Text input at bottom with send button
- Live updates: subscribe to WebSocket events for this session, append new messages

### 2. Message components
- `mobile/src/components/MessageBubble.tsx` -- styled differently per role
- `mobile/src/components/ToolCallResult.tsx` -- compact display of tool call results
- `mobile/src/components/SessionHeader.tsx` -- name, mode, status, back button

### 3. WebSocket integration
- On screen mount, subscribe to session events via EventContext
- Handle `message.created` events to append messages in real-time
- Handle `session.status_changed` to update header badge

## Acceptance Criteria

- [ ] Session detail screen shows message history from the API
- [ ] Messages are styled differently for user, assistant, system, and tool roles
- [ ] User can type and send a message; it appears in the chat
- [ ] New messages from the backend arrive via WebSocket and appear in real-time
- [ ] Session status badge updates live when status changes
- [ ] Mode indicator shows current session mode (brainstorm/interview/planning/execution/review)

## Test Scenarios

### Unit: MessageBubble
- Render with role=user, verify user styling
- Render with role=assistant, verify assistant styling
- Render with role=tool, verify compact tool result display

### Integration: Chat flow
- Mount SessionDetailScreen with mocked API + WebSocket
- Verify messages load from API
- Simulate sending a message, verify it appears in chat
- Simulate WebSocket `message.created` event, verify new message appears

## Dependencies
- Depends on: #53a (scaffolding), #53b (navigation from sessions list)
