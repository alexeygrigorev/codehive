# Issue #130: Subsessions -- sessions can start child sessions with different engines

**STATUS: Split into sub-issues. This is the parent tracking issue.**

## Problem

Currently each session runs a single engine. But a powerful pattern is having one session (e.g., Z.ai agent) orchestrate work by spawning subsessions with different engines (e.g., Claude Code for one task, Codex for another, Gemini for a third).

This enables:
- A Z.ai orchestrator agent that delegates coding tasks to specialized CLI engines
- End-to-end testing of all CLI engines through a single orchestrator session
- Multi-agent collaboration where different AI models work on different parts of a problem

## Research Findings (PM Grooming)

### What already exists

| Component | Status | Location |
|-----------|--------|----------|
| `Session.parent_session_id` FK | Done (#21) | `backend/codehive/db/models.py` line 120-122 |
| `child_sessions` relationship | Done (#21) | `backend/codehive/db/models.py` line 134-137 |
| `list_child_sessions()` | Done (#21) | `backend/codehive/core/session.py` line 164 |
| `GET /sessions/{id}/subagents` API | Done (#21) | `backend/codehive/api/routes/sessions.py` line 201 |
| `SubAgentManager` (spawn, status, report) | Done (#21) | `backend/codehive/core/subagent.py` |
| `spawn_subagent` tool schema | Done (#21) | `backend/codehive/engine/tools/spawn_subagent.py` |
| `query_agent` tool | Done | `backend/codehive/engine/tools/query_agent.py` |
| `send_to_agent` tool | Done | `backend/codehive/engine/tools/send_to_agent.py` |
| Orchestrator mode (restricted tools) | Done | `backend/codehive/engine/orchestrator.py` |
| SubAgentPanel (web) | Done (#23) | `web/src/components/sidebar/SubAgentPanel.tsx` |
| SubAgentTree (web) | Done (#23) | `web/src/components/SubAgentTree.tsx` |
| AggregatedProgress (web) | Done (#23) | `web/src/components/AggregatedProgress.tsx` |
| `fetchSubAgents` API client | Done (#23) | `web/src/api/subagents.ts` |
| AgentCommService (query, send, broadcast) | Done | `backend/codehive/core/agent_comm.py` |

### Key gaps identified

1. **No engine selection**: `SubAgentManager.spawn_subagent()` hardcodes `engine=parent.engine` (line 66 of subagent.py). The tool schema has no `engine` parameter.
2. **No initial message execution**: Spawning creates a DB record but never instantiates the child engine or sends a message. The subsession sits `idle` forever.
3. **No result collection tool**: `collect_report()` exists on SubAgentManager but no tool exposes it. The orchestrator cannot get structured results from a completed subsession.
4. **No list-my-children tool**: The orchestrator must remember session IDs from spawn calls. There is no `list_subsessions` tool.
5. **No engine badge in UI**: SubAgentNode shows name/status but not which engine the child uses.
6. **No inline subsession events**: `subagent.spawned` and `subagent.report` events are published but not rendered in the parent's chat.

### Design decisions

- **Sync execution**: The `spawn_subagent` tool blocks until the child's first turn completes and returns the response. This fits the LLM conversation loop (one tool at a time). Async fan-out is a future enhancement.
- **Engine factory reuse**: SubAgentManager should use the same `_build_engine()` factory from `api/routes/sessions.py` to instantiate engines.
- **Valid engines**: native, claude_code, codex_cli, copilot_cli, gemini_cli, codex (from `_build_engine()` switch).

## Split

This issue is too large for one implementation cycle. Split into 3 sub-issues:

| Sub-issue | Scope | Dependencies |
|-----------|-------|-------------|
| **#130a** -- Subsession engine selection | Backend: add `engine` and `initial_message` params to spawn tool, build engine, execute first turn | None |
| **#130b** -- Subsession result collection | Backend: `get_subsession_result` and `list_subsessions` tools | #130a |
| **#130c** -- Subsession Web UI | Frontend: engine badges, click-through, inline events, real-time updates | #130a, #130b |

Each sub-issue has its own `.groomed.md` file with user stories, acceptance criteria, and test scenarios.

## Log

### [PM] 2026-03-19 12:00

- Researched existing codebase: read models.py, subagent.py, zai_engine.py, orchestrator.py, all tool schemas, SubAgentPanel.tsx, SubAgentTree.tsx, agent_comm.py, sessions.py API routes
- Found substantial existing infrastructure (DB model, tools, UI components) from issues #21, #23, #121
- Identified 6 specific gaps between current state and #130 requirements
- Decided on sync execution model for initial implementation (spawn blocks until first turn completes)
- Split into 3 groomed sub-issues: #130a (engine selection), #130b (result collection), #130c (web UI)
- Created groomed specs: `130a-subsession-engine-selection.groomed.md`, `130b-subsession-result-collection.groomed.md`, `130c-subsession-web-ui.groomed.md`
