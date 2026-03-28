# 154 — Team engine assignment: each agent profile gets an engine/model

## Problem
Agent profiles (#151) have names and personalities but no engine preference. When the orchestrator spawns a sub-agent for "Alice (SWE)", it doesn't know which engine to use.

## Vision
Each agent profile in the team can have a preferred engine and model:
- "Alice (SWE)" → Claude Code, claude-sonnet-4-6
- "Marcus (SWE)" → Codex CLI, gpt-5.4
- "Priya (QA)" → Claude Code, claude-sonnet-4-6
- "Jordan (PM)" → Copilot CLI, default

The orchestrator uses this when spawning sub-agents. If the preferred engine is unavailable, fall back to the next available one.

## Acceptance criteria
- [ ] AgentProfile model gains `preferred_engine` and `preferred_model` fields
- [ ] Default team generation assigns engines based on availability
- [ ] Orchestrator reads agent profile's engine preference when spawning
- [ ] Fallback to any available engine if preferred is unavailable
- [ ] Team CRUD API supports editing engine/model per agent
- [ ] Web UI shows engine assignment on team cards
