# 28: Terminal Client - Session View

## Description
Implement the TUI session view with chat interaction, ToDo list, sub-agent display, timeline, and changed files panels. Connect to the backend WebSocket for live updates.

## Scope
- `backend/codehive/clients/terminal/screens/session.py` -- Session screen layout with panels
- `backend/codehive/clients/terminal/widgets/chat.py` -- Chat panel with message display and input
- `backend/codehive/clients/terminal/widgets/todo.py` -- ToDo list panel
- `backend/codehive/clients/terminal/widgets/timeline.py` -- Action timeline panel
- `backend/codehive/clients/terminal/widgets/files.py` -- Changed files panel
- `backend/codehive/clients/terminal/ws_client.py` -- WebSocket client for real-time updates in TUI
- `backend/tests/test_tui_session.py` -- TUI session view tests

## Dependencies
- Depends on: #27 (TUI app shell and navigation)
- Depends on: #07 (WebSocket endpoint for live events)
- Depends on: #09 (engine adapter for sending messages)
