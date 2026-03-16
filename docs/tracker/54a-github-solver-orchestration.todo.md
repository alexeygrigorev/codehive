# 54a: GitHub Auto-Solve -- Solver Orchestration

## Description
Extend the auto-session trigger (#36) so that when a GitHub issue triggers a session in auto mode, the session actually runs the NativeEngine to solve the issue: read the issue, plan, implement, run tests, and push to main on success.

## Implementation Plan

### 1. Solver module
- `backend/codehive/integrations/github/solver.py`
- `async def solve_issue(db, project_id, issue_id, session_id)` -- main orchestration function
- Steps:
  1. Load the issue from DB (title + description)
  2. Load project knowledge for context
  3. Compose a system prompt: "You are solving GitHub issue #{number}: {title}. {description}. The project uses {tech_stack}. Implement the fix, write tests, and verify they pass."
  4. Send the prompt to the session's NativeEngine via `engine.send_message()`
  5. Wait for the engine to complete (session status becomes `completed` or `failed`)
  6. If completed: run `git add . && git commit -m "Fix #{number}: {title}" && git push origin main` via execution layer
  7. Return result: `{success: bool, commit_sha: str | None, error: str | None}`

### 2. Integration with triggers
- In `triggers.py`, after session creation in auto mode, call `solve_issue()` as a background task
- Use `asyncio.create_task()` so the webhook response is not blocked

### 3. Git push via execution layer
- Use existing `backend/codehive/execution/git_ops.py` for commit
- Add `git_push(project_path, remote, branch)` function if not already present
- Use existing `shell.py` to run `git push`

### 4. Test runner check
- Before pushing, run the project's test command (from knowledge base or default `pytest`)
- If tests fail, do NOT push; mark result as failed with test output

## Acceptance Criteria

- [ ] `solver.py` exists with `solve_issue()` function
- [ ] When auto-mode webhook fires, a session is created AND the solver runs
- [ ] Solver sends the issue content to the NativeEngine as a prompt
- [ ] On success, solver commits and pushes to main
- [ ] On test failure, solver does NOT push and records the failure
- [ ] `uv run pytest tests/test_solver.py -v` passes with 4+ tests

## Test Scenarios

### Unit: Solver logic
- Mock engine returning completed status, verify git push is called
- Mock engine returning failed status, verify git push is NOT called
- Mock test runner failing, verify push is NOT called and error is recorded
- Verify commit message includes issue number and title

### Integration: Trigger to solver
- Mock webhook event, verify session is created and solve_issue is called
- Verify solver loads issue content from DB correctly

## Dependencies
- Depends on: #36 (webhook auto-session), #09 (engine adapter), #08 (execution layer)
