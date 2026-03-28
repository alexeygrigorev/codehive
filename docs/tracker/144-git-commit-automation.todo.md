# 144 — Git commit automation: backend commits after PM accepts

## Problem
After PM accepts a task, someone needs to commit the code. Currently this is done manually by the user or the Claude Code orchestrator. The app itself can't commit.

## Vision
The backend can perform git operations on the project directory:
- Stage changed files
- Create a commit with a conventional message
- Optionally push to remote

This happens automatically when the orchestrator moves a task to `done`.

## Acceptance criteria
- [ ] Git service in backend that can stage, commit, and push
- [ ] Commit message follows convention: "Implement task #N: short description"
- [ ] Orchestrator triggers commit automatically after PM accepts
- [ ] Commit only includes files changed during the task (not unrelated changes)
- [ ] Push is optional and configurable per project
