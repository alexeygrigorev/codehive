# 24: Checkpoint Creation and Rollback

## Description
Implement session checkpoints for safety and rollback. Checkpoints capture git state plus session state (JSONB). Support auto-checkpointing before destructive operations and manual checkpoint creation via API. Rollback restores both git state and session state.

## Scope
- `backend/codehive/core/checkpoint.py` -- Checkpoint creation (git commit + session state snapshot), rollback logic (git restore + state restore), listing
- `backend/codehive/api/schemas/checkpoint.py` -- Pydantic schemas for checkpoint endpoints
- `backend/codehive/api/routes/checkpoints.py` -- CRUD endpoints: list checkpoints for session, create manual checkpoint, rollback to checkpoint
- `backend/codehive/api/app.py` -- Register checkpoint routers
- `backend/codehive/engine/native.py` -- Extend to auto-checkpoint before destructive tool calls (edit_file, run_shell, git_commit)
- `backend/tests/test_checkpoints.py` -- Checkpoint and rollback tests

## Endpoints
- `GET /api/sessions/{session_id}/checkpoints` -- List checkpoints for a session (ordered by created_at desc)
- `POST /api/sessions/{session_id}/checkpoints` -- Create a manual checkpoint (commits current git state, snapshots session state)
- `POST /api/checkpoints/{checkpoint_id}/rollback` -- Rollback to a specific checkpoint (restores git ref + session state)

## Dependencies
- Depends on: #03 (Checkpoint DB model) -- DONE
- Depends on: #08 (git operations for commit/restore) -- DONE
- Depends on: #05 (session state management) -- DONE

## Acceptance Criteria

- [ ] `uv run pytest backend/tests/test_checkpoints.py -v` passes with 8+ tests
- [ ] `POST /api/sessions/{session_id}/checkpoints` creates a checkpoint row in DB with a valid `git_ref` (commit SHA) and `state` (JSONB snapshot of session status, mode, config)
- [ ] `GET /api/sessions/{session_id}/checkpoints` returns a list of checkpoints ordered by `created_at` descending
- [ ] `POST /api/checkpoints/{checkpoint_id}/rollback` restores git working tree to the checkpoint's `git_ref` (via `git checkout` or `git reset`) and restores session status/mode/config from the checkpoint's `state` JSONB
- [ ] Creating a checkpoint for a non-existent session returns 404
- [ ] Rolling back to a non-existent checkpoint returns 404
- [ ] Rolling back updates the session row in the DB (status, mode, config restored from checkpoint state)
- [ ] `core/checkpoint.py` contains reusable functions (`create_checkpoint`, `list_checkpoints`, `rollback_checkpoint`) that are independent of the HTTP layer
- [ ] The `NativeEngine._execute_tool` method calls `create_checkpoint` before executing destructive tools (`edit_file`, `run_shell`, `git_commit`), creating an auto-checkpoint with a descriptive label (e.g., "auto: before edit_file path/to/file")
- [ ] Auto-checkpoints use the existing `GitOps.commit` to create the git ref and store the current session state in the checkpoint's `state` column
- [ ] Pydantic schemas (`CheckpointRead`, `CheckpointCreate`) follow the same pattern as existing schemas in `backend/codehive/api/schemas/`
- [ ] Checkpoint routers are registered in `app.py` following the existing pattern (session-scoped router for list/create, flat router for rollback)

## Test Scenarios

### Unit: core/checkpoint.py
- `create_checkpoint` with a valid session ID creates a Checkpoint row with `git_ref` and `state` populated
- `create_checkpoint` with a non-existent session ID raises `SessionNotFoundError`
- `list_checkpoints` returns checkpoints for a session ordered by `created_at` descending
- `list_checkpoints` for a session with no checkpoints returns an empty list
- `rollback_checkpoint` with a valid checkpoint ID restores session fields (status, mode, config) from checkpoint state
- `rollback_checkpoint` with a non-existent checkpoint ID raises an appropriate error
- `rollback_checkpoint` calls `GitOps.checkout` (or equivalent) with the checkpoint's `git_ref`

### Integration: API endpoints
- `POST /api/sessions/{session_id}/checkpoints` with a valid session returns 201 and a checkpoint with `id`, `session_id`, `git_ref`, `state`, `created_at`
- `POST /api/sessions/{session_id}/checkpoints` with a non-existent session returns 404
- `GET /api/sessions/{session_id}/checkpoints` lists all checkpoints for the session
- `POST /api/checkpoints/{checkpoint_id}/rollback` with a valid checkpoint returns 200 and the updated session state
- `POST /api/checkpoints/{checkpoint_id}/rollback` with a non-existent checkpoint returns 404

### Unit: NativeEngine auto-checkpoint
- Calling `_execute_tool("edit_file", ...)` triggers a checkpoint creation before the edit executes
- Calling `_execute_tool("run_shell", ...)` triggers a checkpoint creation before the shell command executes
- Calling `_execute_tool("read_file", ...)` does NOT trigger a checkpoint (read-only operation)
- Auto-checkpoints store a descriptive label in the checkpoint state (e.g., `{"trigger": "auto", "tool": "edit_file", ...}`)

## Implementation Notes
- The Checkpoint model already exists in `backend/codehive/db/models.py` with fields: `id`, `session_id`, `git_ref`, `state` (JSONB), `created_at`
- `GitOps` already has `commit()` (returns SHA), `checkout()`, and `diff()` methods
- The `state` JSONB should snapshot at minimum: `session.status`, `session.mode`, `session.config`; optionally include a human-readable `label` or `trigger` field
- For rollback, use `git checkout <ref>` for simplicity in the first iteration; a more sophisticated `git reset --hard` approach can be a follow-up if needed
- Follow the router pattern from `sessions.py`: session-scoped router (`/api/sessions/{session_id}/checkpoints`) for list and create, flat router (`/api/checkpoints`) for rollback
- The auto-checkpoint in `NativeEngine` should be best-effort: if checkpoint creation fails (e.g., nothing to commit), the tool call should still proceed with a warning logged

## Log

### [SWE] 2026-03-15 12:00
- Implemented checkpoint creation, listing, and rollback in core/checkpoint.py with reusable functions independent of HTTP layer
- Created Pydantic schemas (CheckpointCreate, CheckpointRead) following existing patterns
- Created API routes with session-scoped router for list/create and flat router for rollback
- Registered checkpoint routers in app.py
- Extended NativeEngine._execute_tool with best-effort auto-checkpoint before destructive tools (edit_file, run_shell, git_commit) with descriptive labels
- Auto-checkpoint failures are logged as warnings and do not block tool execution
- Files created: backend/codehive/core/checkpoint.py, backend/codehive/api/schemas/checkpoint.py, backend/codehive/api/routes/checkpoints.py, backend/tests/test_checkpoints.py
- Files modified: backend/codehive/api/app.py, backend/codehive/engine/native.py
- Tests added: 19 tests (9 unit core, 6 integration API, 4 auto-checkpoint engine)
- Build results: 375 tests pass (full suite), 0 fail, ruff clean
- Known limitations: none

### [QA] 2026-03-15 12:30
- Tests: 19 passed in test_checkpoints.py, 375 passed full suite, 0 failed
- Ruff: clean (check and format)
- Acceptance criteria:
  1. 19 tests pass (8+ required): PASS
  2. POST creates checkpoint with git_ref and state JSONB: PASS
  3. GET returns checkpoints ordered by created_at desc: PASS
  4. POST rollback restores git state and session state: PASS
  5. Creating checkpoint for non-existent session returns 404: PASS
  6. Rolling back to non-existent checkpoint returns 404: PASS
  7. Rollback updates session row in DB (status, mode, config): PASS
  8. core/checkpoint.py has reusable functions independent of HTTP: PASS
  9. NativeEngine auto-checkpoints before destructive tools with descriptive labels: PASS
  10. Auto-checkpoints use GitOps.commit and store session state: PASS
  11. Pydantic schemas follow existing patterns: PASS
  12. Checkpoint routers registered in app.py following existing pattern: PASS
- Code quality: type hints present, proper error handling, no hardcoded values, follows existing patterns consistently
- VERDICT: PASS

### [PM] 2026-03-15 13:00
- Reviewed diff: 6 files changed (4 new, 2 modified in backend scope)
  - New: core/checkpoint.py, api/schemas/checkpoint.py, api/routes/checkpoints.py, tests/test_checkpoints.py
  - Modified: api/app.py (router registration), engine/native.py (auto-checkpoint logic)
- Results verified: real data present -- 19/19 tests pass in test_checkpoints.py, 375/375 full suite, ruff clean
- Acceptance criteria: all 12 met
  1. 19 tests pass (8+ required): MET
  2. POST creates checkpoint with git_ref and state JSONB: MET -- commit SHA stored, session status/mode/config snapshotted
  3. GET returns checkpoints ordered by created_at desc: MET -- query uses .order_by(created_at.desc())
  4. POST rollback restores git state and session state: MET -- calls git_ops.checkout + restores session fields
  5. Creating checkpoint for non-existent session returns 404: MET
  6. Rolling back to non-existent checkpoint returns 404: MET
  7. Rollback updates session row in DB: MET -- status/mode/config restored, committed, refreshed
  8. core/checkpoint.py has reusable functions independent of HTTP: MET -- no FastAPI imports
  9. NativeEngine auto-checkpoints before destructive tools: MET -- edit_file, run_shell, git_commit trigger; read_file does not
  10. Auto-checkpoints use GitOps.commit and store session state: MET -- delegates to create_checkpoint
  11. Pydantic schemas follow existing patterns: MET -- ConfigDict(from_attributes=True), Field constraints
  12. Checkpoint routers registered in app.py following existing pattern: MET -- session-scoped + flat routers
- Code quality notes:
  - Auto-checkpoint is best-effort with warning log on failure (does not block tool execution) -- matches spec
  - _execute_tool uses keyword-only optional params (session_id, db) to avoid breaking existing callers
  - Proper error hierarchy: SessionNotFoundError, CheckpointNotFoundError
  - Tests cover unit (core), integration (API), and engine (auto-checkpoint) layers
- Follow-up issues created: none needed
- VERDICT: ACCEPT
