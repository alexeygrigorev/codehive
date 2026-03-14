# 33: Claude Code CLI Wrapper and Event Parser

## Description
Build a wrapper around the Claude Code CLI (`claude`) that spawns it as a subprocess per session, captures its stdout/stderr output, and parses it into codehive's unified event format.

## Scope
- `backend/codehive/engine/claude_code.py` -- Claude Code CLI process manager: spawn, send input, capture output, terminate
- `backend/codehive/engine/claude_code_parser.py` -- Parse Claude Code CLI output into codehive events (message.created, tool.call.started, tool.call.finished, file.changed, etc.)
- `backend/tests/test_claude_code_wrapper.py` -- Wrapper and parser tests (with mocked CLI output)

## Behavior
- Spawns `claude` CLI as async subprocess per session
- Routes user messages as stdin to the process
- Parses structured stdout into codehive event stream
- Handles process lifecycle (start, stop, crash recovery)
- Respects Claude Code's own approval flow

## Dependencies
- Depends on: #07 (event bus for publishing parsed events)
