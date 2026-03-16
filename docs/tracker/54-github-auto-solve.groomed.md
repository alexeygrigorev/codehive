# 54: GitHub Issue Auto-Solve (Parent)

## Description
When a GitHub issue is created (via webhook in auto mode), codehive automatically creates a session, solves the issue, pushes the fix directly to main, and closes the GitHub issue. No PR needed. Split into two sub-issues.

## Sub-Issues
- **54a** -- Solver orchestration: session runs, agent works, tests pass, git push to main
- **54b** -- GitHub issue close + error handling: close via API, comment with commit SHA, failure comments

## Dependencies
- Depends on: #35 (GitHub import), #36 (webhook auto-session), #09 (engine adapter)
