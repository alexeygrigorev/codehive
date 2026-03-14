# 22: Orchestrator Mode

## Description
Implement orchestrator mode for sessions. In this mode, the agent plans, decomposes tasks, and spawns sub-agents but does NOT edit files directly. The orchestrator monitors sub-agent progress via events and aggregates their reports to decide next steps.

## Scope
- `backend/codehive/engine/orchestrator.py` -- Orchestrator agent logic: plan, decompose, spawn, monitor, aggregate
- `backend/codehive/core/session.py` -- Enforce orchestrator restrictions (no file edit tools when mode=orchestrator)
- `backend/codehive/engine/native.py` -- Extend tool filtering based on session mode
- `backend/tests/test_orchestrator.py` -- Orchestrator mode tests

## Behavior
- When session mode is "orchestrator", file-editing tools are removed from the tool set
- Orchestrator receives sub-agent completion events and structured reports
- Orchestrator can spawn multiple sub-agents in parallel
- Orchestrator aggregates progress and decides: spawn more, fix issues, or mark complete

## Dependencies
- Depends on: #21 (sub-agent spawning)
- Depends on: #09 (engine adapter)
