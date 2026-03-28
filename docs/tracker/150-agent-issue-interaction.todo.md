# 150 — Agent issue interaction: create, read, write via tools

## Problem
Agents need a clear, documented way to interact with the issue tracker. Currently the orchestrator manages issues, but individual agents (PM, SWE, QA) should be able to:
1. **Create issues** — PM discovers a new requirement, SWE finds a bug
2. **Read issues** — SWE reads acceptance criteria, QA reads the full spec
3. **Write to issues** — All agents append log entries with their findings

## Expected behavior
Three tools available to agents during sessions:
- `read_issue` — fetch issue details including acceptance criteria and log entries
- `write_issue_log` — append a log entry (agent role, content, evidence)
- `create_issue` — create a new issue in the backlog (already partially done in #145)

## Acceptance criteria
- [ ] `read_issue` tool: returns issue title, description, acceptance_criteria, status, and log entries
- [ ] `write_issue_log` tool: appends a log entry with agent_role and content
- [ ] `create_issue` tool: creates issue in backlog (extend existing create_task tool)
- [ ] Tools are available to all agent roles (PM, SWE, QA, OnCall)
- [ ] Issue log entries show which agent wrote them (role + session info)
- [ ] Tools work through the engine adapter (not just Z.ai — also via CLI engines)
- [ ] Web UI shows agent log entries with role attribution
