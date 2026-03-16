# 54: GitHub Issue Auto-Solve

## Description
When a GitHub issue is created (via webhook in auto mode), codehive automatically creates a session, solves the issue, pushes the fix directly to main, and closes the GitHub issue. No PR needed.

## Scope
- `backend/codehive/integrations/github/solver.py` — Auto-solve orchestration
- `backend/codehive/integrations/github/triggers.py` — Extend auto mode to trigger solver
- `backend/codehive/integrations/github/push.py` — Git push + GitHub issue close via `gh` CLI or API

## Behavior
1. Webhook receives new GitHub issue (auto mode enabled)
2. Issue imported into codehive tracker (existing #35)
3. Session created automatically (existing #36)
4. Agent starts working: reads issue, plans, implements, tests
5. On success: `git add . && git commit && git push origin main`
6. Close GitHub issue via API with comment linking the commit
7. On failure: leave issue open, add comment with error details

## Key requirements
- Use existing NativeEngine to do the work
- Push directly to main (no branch, no PR)
- Close issue via GitHub API (httpx POST to /repos/{owner}/{repo}/issues/{number})
- Add commit SHA in the closing comment
- If tests fail, don't push — leave issue open with failure details

## Dependencies
- Depends on: #35 (GitHub import), #36 (webhook auto-session), #09 (engine adapter)
