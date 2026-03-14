# 27: Terminal Client - Dashboard and Navigation

## Description
Build the Textual TUI application shell with a dashboard showing active projects, sessions, pending questions, and failed agents. Implement keyboard-driven navigation between views.

## Scope
- `backend/codehive/clients/terminal/app.py` -- Textual App subclass, main entry point
- `backend/codehive/clients/terminal/screens/dashboard.py` -- Dashboard screen: active projects, sessions, pending items
- `backend/codehive/clients/terminal/screens/project_list.py` -- Project list with navigation
- `backend/codehive/clients/terminal/screens/project_detail.py` -- Single project: issues, sessions, status
- `backend/codehive/clients/terminal/widgets/` -- Reusable TUI widgets (status indicator, table)
- `backend/codehive/cli.py` -- Add `codehive tui` command to launch the TUI
- `backend/tests/test_tui.py` -- TUI widget and screen tests

## Dependencies
- Depends on: #04 (project CRUD API)
- Depends on: #05 (session CRUD API)
- Depends on: #10 (pending questions API)
