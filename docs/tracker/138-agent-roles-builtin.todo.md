# 138 — Built-in agent roles: PM, SWE, QA, OnCall

## Problem
Agent roles are currently defined in .claude/agents/*.md files. The app doesn't know about roles — it just spawns generic sessions. The pipeline can't enforce "only a PM can groom" or "only QA can verify."

## Vision
Agent roles are first-class in the app:
- Each role has a system prompt, allowed actions, and pipeline permissions
- When a task needs grooming, the app spawns a PM session automatically
- When a task needs implementation, the app spawns an SWE session
- The role determines what the agent can do (PM can't write code, SWE can't accept)

## What this looks like
- Role model: name, system_prompt, allowed_pipeline_transitions, tools
- Predefined roles: PM, SWE, QA, OnCall
- Session has a `role` field — determines what the session can do
- API enforces role-based permissions on task transitions
- Web UI shows role badges on sessions

## Acceptance criteria
- [ ] Role model with predefined PM/SWE/QA/OnCall roles
- [ ] Sessions have an assigned role
- [ ] Task transitions validate that the correct role is performing them
- [ ] Role system prompts are stored in the DB (editable via API)
- [ ] Web UI shows role badges
