# 18: WebSocket Client for Real-Time Updates

## Description
Implement the WebSocket client in the web app that connects to the backend event bus. Provides live message streaming, ToDo status updates, diff updates, and notification badges for pending questions and approvals.

## Scope
- `web/src/api/websocket.ts` -- WebSocket connection manager (connect, reconnect, subscribe to session events)
- `web/src/hooks/useSessionEvents.ts` -- React hook for subscribing to session events
- `web/src/hooks/useNotifications.ts` -- React hook for pending questions / approval notification badges
- `web/src/context/WebSocketContext.tsx` -- React context provider for shared WebSocket state

## Dependencies
- Depends on: #14 (React app scaffolding)
- Depends on: #07 (backend WebSocket endpoint and event bus)
