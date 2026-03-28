# 160 — Orchestrator tool: spawn team agent with task assignment

## Problem
The orchestrator (main agent) needs a tool to start a team member and assign them a task. Currently the orchestrator service spawns agents programmatically in the pipeline loop, but the main chat agent can't do this interactively.

## Vision
The main agent in a session should be able to:
1. Pick a team member (e.g., "Alice (SWE)")
2. Assign them a task from the tracker
3. Start them as a sub-agent with the right engine, model, and system prompt
4. Monitor their progress

## What this looks like
A `spawn_team_agent` tool available to the orchestrator:
```
spawn_team_agent(
  agent_profile_id: "uuid",   # which team member
  task_id: "uuid",             # which task to work on
  instructions: "Implement the sidebar fix per the acceptance criteria"
)
```

The tool:
- Looks up the agent profile (name, role, preferred_engine, personality)
- Creates a child session bound to the task
- Sends the initial message with instructions + task context
- Returns the session ID so the orchestrator can check progress later

## Acceptance criteria
- [ ] `spawn_team_agent` tool schema with agent_profile_id, task_id, instructions
- [ ] Tool handler creates child session with correct engine from agent profile
- [ ] Child session is bound to the task (task_id + pipeline_step)
- [ ] Agent profile's personality/system_prompt_modifier applied to the session
- [ ] Tool returns session_id for progress tracking
- [ ] Available in orchestrator mode
- [ ] Works with existing get_subsession_result / list_subsessions tools
