# Issue #94: Unified session model -- project = folder, sessions accessible from all clients

**Status: SPLIT into sub-issues. Do not implement this file directly.**

## Mental Model

- A **project** is a folder on disk (e.g., `/home/alexey/git/myapp`)
- A project can have multiple **sessions** (conversations with the agent)
- Sessions are accessible from **any client**: web, mobile, terminal, Telegram
- The terminal (`codehive code`) is just another client connecting to the same sessions

## Current Problem

`codehive code` runs a standalone NativeEngine with a `_NoOpEventBus` -- it doesn't connect to the backend at all. Sessions created from the terminal are invisible to web/mobile, and vice versa.

## Sub-Issues

This issue is too large for a single implementation pass. It touches the backend API (new endpoints), CLI argument parsing, CodeApp client logic (two modes: backend-connected vs local-only), and WebSocket streaming. It is split into three parts with a clear dependency chain:

1. **#94a -- Project-by-path API and auto-create** (`94a-project-by-path-api.todo.md`)
   - Add `GET /api/projects/by-path?path=...` endpoint to look up a project by its disk path
   - Add `get_project_by_path()` to `core/project.py`
   - Add auto-create logic: if no project exists for a path, create one (name = folder basename)
   - No CLI or TUI changes -- just backend plumbing

2. **#94b -- `codehive code` connects to backend** (`94b-code-connects-to-backend.todo.md`)
   - Depends on #94a
   - `codehive code [directory]` tries backend first: resolves project by path, picks/creates session, runs engine via backend API
   - Falls back to local-only mode (current behavior) when backend is not reachable
   - New CLI flags: `--session <id>`, `--new`
   - CodeApp gets a second mode: backend-connected (sends messages via API, receives events via WebSocket)

3. **#94c -- Cross-client session visibility** (`94c-cross-client-session-visibility.todo.md`)
   - Depends on #94b
   - When terminal is running a session through the backend, web/mobile see the same chat history in real time
   - WebSocket streaming of engine events to all connected clients
   - User can type messages from web into the same backend-managed session
   - This is largely verification/integration work -- the WebSocket infrastructure already exists

## Dependencies

- #88b (remove workspaces) should be `.done.md` first -- projects become top-level without workspace_id, which simplifies the project-by-path auto-create logic
- #93 (SQLite lightweight mode) is recommended but not strictly required -- if the backend uses SQLite, `codehive serve` works with zero infrastructure, making the "backend-connected" path the default

## Completion

This parent issue is complete when all three sub-issues (#94a, #94b, #94c) are `.done.md`.

## Notes

- The backend already has session CRUD, message sending, and WebSocket streaming
- The key change is making `codehive code` use the backend API instead of a local engine
- The fallback to local-only mode preserves the "works without infrastructure" promise
- This subsumes the current standalone `CodeApp` behavior as the fallback path
