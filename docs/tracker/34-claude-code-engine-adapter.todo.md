# 34: Claude Code Engine Adapter

## Description
Implement the EngineAdapter interface for Claude Code, connecting the CLI wrapper to the session system. Sessions can be created with `engine: claude_code` and use the same UI, task management, and diff viewer as native sessions.

## Scope
- `backend/codehive/engine/claude_code.py` -- Extend with full EngineAdapter protocol implementation (create_session, send_message, start_task, pause, resume, approve_action, reject_action, get_diff)
- `backend/codehive/api/routes/sessions.py` -- Extend session creation to accept engine selection
- `backend/tests/test_claude_code_engine.py` -- Engine adapter tests

## Dependencies
- Depends on: #33 (Claude Code CLI wrapper)
- Depends on: #09 (engine adapter interface)
