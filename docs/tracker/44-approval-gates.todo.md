# 44: Approval Gates

## Description
Implement configurable approval gates that require user confirmation before destructive or sensitive operations. Define which actions require approval (file deletion, force push, migration apply, production commands, secret-related edits) and enforce them in the engine.

## Scope
- `backend/codehive/core/approval.py` -- Approval policy engine: define rules, check actions against rules, create approval requests, process responses
- `backend/codehive/api/routes/approvals.py` -- Endpoints: list pending approvals, approve/reject, configure approval policy per session/project
- `backend/codehive/engine/native.py` -- Extend tool execution to check approval policy before running, pause and emit `approval.required` event when needed
- `backend/tests/test_approvals.py` -- Approval policy and gate tests

## Default approval-required actions
- File deletion
- Force push (`git push --force`)
- Database migration apply
- Production/deployment commands
- Secret-related file edits

## Dependencies
- Depends on: #09 (engine adapter for intercepting tool calls)
- Depends on: #07 (event bus for approval.required events)
