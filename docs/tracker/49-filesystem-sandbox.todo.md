# 49: Filesystem Sandbox and Command Policy

## Description
Implement security controls for agent execution: filesystem sandboxing (confine agent to project root, prevent symlink escapes) and command policy (allowlist/denylist for shell commands, configurable network access, package install confirmation).

## Scope
- `backend/codehive/execution/sandbox.py` -- Filesystem sandbox: path validation, symlink detection, hidden directory policy
- `backend/codehive/execution/policy.py` -- Command policy engine: allowlist/denylist rules, categorize commands (read-only, write, destructive, network), enforce policy before execution
- `backend/codehive/execution/shell.py` -- Extend to enforce sandbox and policy before running commands
- `backend/codehive/execution/file_ops.py` -- Extend to enforce sandbox on all file operations
- `backend/tests/test_sandbox.py` -- Sandbox and policy tests

## Dependencies
- Depends on: #08 (execution layer)
