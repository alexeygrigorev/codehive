# 24: Checkpoint Creation and Rollback

## Description
Implement session checkpoints for safety and rollback. Checkpoints capture git state plus session state (JSONB). Support auto-checkpointing before destructive operations and manual checkpoint creation via UI/CLI. Rollback restores both git state and session state.

## Scope
- `backend/codehive/core/checkpoint.py` -- Checkpoint creation (git commit + session state snapshot), rollback logic (git restore + state restore)
- `backend/codehive/api/routes/checkpoints.py` -- CRUD endpoints: list checkpoints for session, create manual checkpoint, rollback to checkpoint
- `backend/codehive/engine/native.py` -- Extend to auto-checkpoint before destructive tool calls
- `backend/tests/test_checkpoints.py` -- Checkpoint and rollback tests

## Endpoints
- `GET /api/sessions/{session_id}/checkpoints` -- List checkpoints
- `POST /api/sessions/{session_id}/checkpoints` -- Create manual checkpoint
- `POST /api/checkpoints/{id}/rollback` -- Rollback to checkpoint

## Dependencies
- Depends on: #03 (Checkpoint DB model)
- Depends on: #08 (git operations for commit/restore)
- Depends on: #05 (session state management)
