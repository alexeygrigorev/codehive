# 54: GitHub Issue Auto-Solve (Parent)

## Description
When a GitHub issue is created (via webhook in auto mode), codehive automatically creates a session, solves the issue, pushes the fix directly to main, and closes the GitHub issue. No PR needed. Split into two sub-issues.

## Sub-Issues
- **54a** -- Solver orchestration: session runs, agent works, tests pass, git push to main
- **54b** -- GitHub issue close + error handling: close via API, comment with commit SHA, failure comments

## Dependencies
- Depends on: #35 (GitHub import), #36 (webhook auto-session), #09 (engine adapter)

## Log

### [SWE] 2026-03-18 20:55
- This is a parent/umbrella issue. Both sub-issues are already implemented and accepted:
  - #54a (solver orchestration): DONE -- `solver.py` with `solve_issue()`, `SolveResult`, `build_solver_prompt()`; `GitOps.push()` added; triggers.py integration with `asyncio.create_task()`
  - #54b (issue close + error handling): DONE -- `closer.py` with `close_github_issue()`, `comment_failure()`; solver.py updated to call closer functions; internal issue status updates
- No additional code needed for the parent issue
- Verification results:
  - TypeScript check: clean
  - Vitest: 613 passed (107 test files)
  - Ruff check: clean
  - Ruff format: 1 pre-existing file (usage.py) needs formatting, not related to this issue
  - Backend tests: 1855 passed, 7 failed (pre-existing test_ci_pipeline.py failures), 1 collection error (pre-existing test_models.py import error)
  - Solver + closer tests specifically: 26/26 passed
- Files relevant to this feature:
  - `backend/codehive/integrations/github/solver.py`
  - `backend/codehive/integrations/github/closer.py`
  - `backend/codehive/execution/git_ops.py` (push method)
  - `backend/codehive/integrations/github/triggers.py` (auto-mode integration)
  - `backend/tests/test_solver.py` (16 tests)
  - `backend/tests/test_closer.py` (10 tests)
