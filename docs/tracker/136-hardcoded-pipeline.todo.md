# 136 — Hard-coded pipeline: enforce PM → SWE → QA → PM accept

## Problem
Currently the pipeline (PM grooms → SWE implements → QA verifies → PM accepts) is described in PROCESS.md and enforced by prompting. The orchestrator can ignore it, skip steps, or go straight to implementation.

## Vision
The pipeline should be enforced by the application itself. When a task is created in Codehive:
1. It enters a backlog
2. The orchestrator cannot skip steps — the app only allows the next valid transition
3. Each step has a required role (PM, SWE, QA)
4. The app tracks which step each task is in and only allows valid state transitions

## What this looks like
- Task model has a `status` field with values: `backlog` → `grooming` → `groomed` → `implementing` → `testing` → `accepting` → `done`
- API endpoints enforce valid transitions (e.g., can't move to `implementing` without going through `grooming` first)
- Each transition records who did it (which agent/session)
- The web UI shows tasks in a kanban-style pipeline view

## Acceptance criteria
- [ ] Task model has pipeline status with enforced state machine
- [ ] Invalid transitions return 400 errors
- [ ] Each transition is logged with timestamp and agent
- [ ] Web UI shows pipeline stages with tasks in each
- [ ] Tasks can only move forward (or back on rejection) through defined transitions
