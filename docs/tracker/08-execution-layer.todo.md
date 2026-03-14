# 08: Execution Layer

## Description
Core execution tools: shell runner, file operations, git operations, and diff computation. These are the tools the agent engine will use.

## Scope
- `backend/codehive/execution/shell.py` — Async subprocess execution with stdout/stderr streaming, timeout, working directory
- `backend/codehive/execution/file_ops.py` — Read, write, edit files (sandboxed to project root)
- `backend/codehive/execution/git_ops.py` — Status, diff, commit, checkout, branch, log
- `backend/codehive/execution/diff.py` — Compute file diffs, track changed files per session
- `backend/tests/test_execution.py` — Tests for each module

## Key requirements
- Shell runner must stream output (not just return at the end)
- File ops must enforce sandbox (no access outside project root, no symlink escapes)
- Git ops work on the project's repository
- Diff service computes unified diffs between current state and last checkpoint/commit

## Dependencies
- Depends on: #03 (needs Event model for logging tool calls)
