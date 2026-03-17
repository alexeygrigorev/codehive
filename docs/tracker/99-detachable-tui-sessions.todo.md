# Issue #99: Detachable TUI sessions — give task and close terminal

## Problem

Currently `codehive code` runs the engine in-process. If you close the terminal, the session dies. When connected to the backend, the session should continue running server-side after the TUI disconnects — like tmux but for agent sessions.

## Requirements

- [ ] When connected to backend: sending a message dispatches it to the backend API, the engine runs server-side
- [ ] Closing the terminal (Ctrl+Q, SSH disconnect, etc.) does NOT stop the agent — it keeps working
- [ ] Reconnecting (`codehive code` again) shows the latest state: messages since disconnect, current status
- [ ] New messages that arrived while disconnected are loaded from history on reconnect
- [ ] If the agent finished while you were away, show the final response
- [ ] If the agent is still running, resume live streaming from where it is
- [ ] Status indicator: "connected (live)" vs "reconnected (catching up)"

## Behavior

```
# Start a session, give it a task
$ codehive code
> Refactor the auth module to use dependency injection

# Agent starts working... close the terminal
# (agent continues on the server)

# Come back later
$ codehive code
# Shows: the agent's full response, tool calls, final message
# If still running: resumes live streaming
```

## Notes

- This depends on #94 (unified sessions) — TUI must use backend API, not local engine
- The backend already runs the engine and stores events in DB + publishes to Redis
- The TUI just needs to: POST message → disconnect → reconnect → load history + resume WS
- Local-only fallback (no backend) cannot support this — session dies with the process
