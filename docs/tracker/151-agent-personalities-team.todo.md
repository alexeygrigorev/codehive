# 151 — Agent personalities and team generation

## Problem
Agents are generic — they have roles (PM, SWE, QA) but no personality, name, or identity. When reading issue logs, all entries look the same. There's no sense of a "team" working on the project.

## Vision
When a project is created, a team of agents is generated:
- Each agent gets a **name** (e.g., "Alice", "Marcus", "Priya")
- Each agent gets a **personality** that shapes their communication style
- Each agent gets an **avatar** (generated or selected from a set)
- The team composition is configurable (e.g., 2 SWEs, 2 QAs, 1 PM, 1 OnCall)

When agents write to issues, their entries show their name and avatar instead of just "SWE" or "QA".

## What this looks like
- Project has a `team` field with a list of agent profiles
- Each profile: `{name, role, personality, avatar_url, system_prompt_modifier}`
- When the orchestrator spawns a session, it assigns a specific team member
- Issue log entries reference the team member, not just the role
- Web UI shows avatar + name on log entries and session cards

## Default team (generated on project creation)
- **PM**: 1 agent
- **SWE**: 2 agents
- **QA**: 2 agents
- **OnCall**: 1 agent (optional)

## Acceptance criteria
- [ ] AgentProfile model: name, role, personality, avatar_url, system_prompt_modifier
- [ ] Project has a team (list of AgentProfiles)
- [ ] Default team generated on project creation
- [ ] Orchestrator assigns specific team members when spawning sessions
- [ ] Issue log entries include agent name and avatar
- [ ] Web UI shows avatars on issue logs and session cards
- [ ] Team is editable via API (add/remove/update agents)
- [ ] Avatar set included (at least 10 distinct avatars)
