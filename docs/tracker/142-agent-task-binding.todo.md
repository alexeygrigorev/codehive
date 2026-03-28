# 142 — Agent ↔ Task binding: link sessions to pipeline steps

## Problem
When the orchestrator spawns an agent session to work on a task, there's no link between them. The app can't tell which session is working on which task at which pipeline step. When the session ends, results don't flow back to the task.

## Vision
- Sessions have `task_id` and `pipeline_step` fields
- When an agent is spawned for a task, the binding is recorded
- When the session ends, the orchestrator knows which task to update
- The UI can show "Session X is grooming Task #5"

## Acceptance criteria
- [ ] Session model has `task_id` (FK to task) and `pipeline_step` (enum) fields
- [ ] API to query sessions by task_id
- [ ] When spawning an agent for a task, binding is set automatically
- [ ] Pipeline UI can show which agent is working on which task
