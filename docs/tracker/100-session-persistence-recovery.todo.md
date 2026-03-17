# Issue #100: Session persistence and recovery after restart

## Problem

If the codehive process is killed while sessions are actively executing (agent mid-conversation, running tools, etc.), all in-flight work is lost. When the server restarts, those sessions show as "executing" in the DB but nothing is actually running. There's no mechanism to detect and resume interrupted sessions.

## Requirements

### Session state tracking
- [ ] Sessions have clear lifecycle states: `idle`, `executing`, `waiting_input`, `completed`, `failed`, `interrupted`
- [ ] When a session is actively running (engine processing), its status is `executing`
- [ ] When the engine finishes a turn and waits for user input, status is `waiting_input`
- [ ] When the user hasn't responded yet but no engine is running, status is `idle`
- [ ] When a session was executing but the process died, status should be marked `interrupted` on recovery

### Startup recovery
- [ ] On `codehive serve` startup, scan for sessions with status `executing`
- [ ] Mark them as `interrupted` (they were mid-execution when the process died)
- [ ] Show interrupted sessions prominently in the UI (web, TUI)
- [ ] User can choose to: resume (re-send the last message), or leave as-is

### Resume mechanism
- [ ] "Resume" action on an interrupted session: re-sends the last user message to the engine
- [ ] The engine picks up with the conversation history from DB
- [ ] If the session was mid-tool-call, the tool call is lost — but the conversation context is preserved

### Graceful shutdown
- [ ] On SIGTERM/SIGINT, mark active sessions as `interrupted` before exiting
- [ ] Flush any pending events to DB

## Notes

- The conversation history is already persisted in the events table
- The engine's in-memory state (tool call results, pending API response) is lost on crash — that's acceptable
- The key insight: we're not trying to resume mid-tool-call, just resume the conversation from the last known state
- This ties into #99 (detachable sessions) — a detached session that finishes normally goes to `completed`, one that crashes goes to `interrupted`
