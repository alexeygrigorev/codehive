# Issue #94: Unified session model — project = folder, sessions accessible from all clients

## Mental Model

- A **project** is a folder on disk (e.g., `/home/alexey/git/myapp`)
- A project can have multiple **sessions** (conversations with the agent)
- Sessions are accessible from **any client**: web, mobile, terminal, Telegram
- The terminal (`codehive code`) is just another client connecting to the same sessions

## Current Problem

`codehive code` runs a standalone NativeEngine with a `_NoOpEventBus` — it doesn't connect to the backend at all. Sessions created from the terminal are invisible to web/mobile, and vice versa.

## Requirements

### `codehive code [directory]` behavior

1. **If backend is running** (default):
   - Look up or create a project for the given directory
   - List existing sessions for that project
   - If no sessions exist, create one automatically
   - If sessions exist, connect to the most recent one (or let user pick)
   - Session runs through the backend API — events stream to all connected clients
   - Web/mobile can see the same session and its history

2. **If backend is not running** (fallback):
   - Print a warning: "Backend not available, starting local-only session"
   - Start a standalone session (current behavior with NativeEngine + NoOpEventBus)
   - Session history is local only, not synced to DB

3. **Session continuity**:
   - `codehive code` with no args → uses current directory, resumes last session
   - `codehive code --session <id>` → connect to a specific session
   - `codehive code --new` → always create a new session
   - Session messages/history are stored in the DB when connected to backend

### Project = folder mapping
- [ ] When `codehive code /path/to/folder` runs, check if a project exists with that path
- [ ] If not, auto-create one (name = folder basename)
- [ ] The project's `path` field in the DB maps to the actual directory on disk

### Web/mobile session view
- [ ] When viewing a session in the web UI, show the same chat history
- [ ] WebSocket streaming works — if terminal is running a session, web sees live updates
- [ ] User can type messages from web into the same session (shared input)

## Notes

- The backend already has session CRUD, message sending, and WebSocket streaming
- The key change is making `codehive code` use the backend API instead of a local engine
- The fallback to local-only mode preserves the "works without infrastructure" promise
- This subsumes the current standalone `CodeApp` behavior as the fallback path
