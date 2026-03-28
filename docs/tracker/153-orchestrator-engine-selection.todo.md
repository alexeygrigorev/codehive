# 153 — Orchestrator engine selection: API-based main agent

## Problem
When starting a new session, the user has to pick a model but doesn't see Claude models (CLI-based engines don't have API models). The session concept conflates the orchestrator (which needs an API engine like Z.ai or OpenAI) with the sub-agents (which use CLI engines like Claude Code, Codex, etc.).

## Vision
The session's main agent (orchestrator) should be an API-based engine (Z.ai or OpenAI) that coordinates work. It spawns sub-agents via CLI engines (Claude Code, Codex, Copilot, Gemini) to do actual coding work.

When creating a new session:
- User selects the **orchestrator engine** (Z.ai, OpenAI) — these are the API providers
- The orchestrator then spawns sub-agents using CLI engines as needed
- The model dropdown should only show API-compatible models for the orchestrator

## Acceptance criteria
- [ ] New session dialog separates "orchestrator engine" (API) from "sub-agent engines" (CLI)
- [ ] Only API providers (Z.ai, OpenAI) shown for the orchestrator selection
- [ ] All providers (CLI and API) are available as sub-agent engines (Z.ai can be both orchestrator and sub-agent)
- [ ] Default orchestrator engine is the first available API provider
- [ ] Session model stores orchestrator engine separately from sub-agent preferences
