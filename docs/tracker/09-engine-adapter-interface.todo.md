# 09: Engine Adapter Interface

## Description
Define the engine adapter protocol and implement the native engine using the Anthropic SDK.

## Scope
- `backend/codehive/engine/base.py` — EngineAdapter Protocol (create_session, send_message, start_task, pause, resume, approve_action, reject_action, get_diff)
- `backend/codehive/engine/native.py` — Native engine: Anthropic SDK conversation loop with tool use
- `backend/tests/test_engine.py` — Engine tests (with mocked LLM responses)

## Native engine behavior
- Uses Anthropic SDK (Claude) as the LLM
- Defines tools: edit_file, read_file, run_shell, git_commit, search_files (using execution layer from #08)
- Runs conversation loop: user message -> LLM response -> tool calls -> tool results -> LLM response -> ...
- Emits events via the event bus (#07) for every message and tool call
- Respects session state machine (pause, resume)

## Dependencies
- Depends on: #07 (event bus), #08 (execution layer)
