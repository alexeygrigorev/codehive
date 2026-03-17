# Issue #97: Fix web chat — messages not displaying

## Problem

When sending a message in a web session, the user's message appears but no assistant response is shown in the chat. The timeline sidebar shows raw events (message.delta, tool calls) arriving, so the backend is working — the chat panel just isn't rendering them.

## Investigation needed

- Is the WebSocket connection established? Check browser console for WS errors
- Are events reaching the ChatPanel component? (useSessionEvents hook)
- Is the event format matching what ChatPanel expects? (event.data.role, event.data.content)
- Is the sendMessage API returning successfully?
- Does the backend's message endpoint actually trigger the engine and publish events?

## Requirements

- [ ] Sending a message in web chat should show the assistant's response
- [ ] Streaming deltas should render live (token by token)
- [ ] Tool calls should show inline
- [ ] Messages should persist — refreshing the page should show history
- [ ] Add console logging in dev mode to debug event flow

## Notes

- The engine streams message.delta events followed by a final message.created
- The WebSocket relay publishes events to channel `session:{id}:events`
- ChatPanel filters for message.created, message.delta, tool.call.started, tool.call.finished
- Check if the event shape from WebSocket matches what ChatPanel expects (id, type, data.role, data.content)
