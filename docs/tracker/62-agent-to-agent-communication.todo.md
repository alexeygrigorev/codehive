# 62: Agent-to-Agent Communication

## Description
Enable agents in a session tree to communicate with each other. The orchestrator should be able to check what a sub-agent is doing right now, and agents in the same team should be able to share context.

## Key scenarios
1. **Orchestrator observes sub-agent** — orchestrator queries a running sub-agent's current state (last N events, current task, status)
2. **Agent asks another agent** — one sub-agent can send a message to a sibling sub-agent and get a response
3. **Shared context** — agents working on the same project share a context channel (like a team chat)

## Scope
- `backend/codehive/core/agent_comm.py` — communication primitives
- `backend/codehive/engine/tools/query_agent.py` — tool for querying another agent's state
- `backend/codehive/engine/tools/send_to_agent.py` — tool for sending a message to another agent
- `backend/codehive/core/events.py` — new event types (agent.query, agent.message)
- `backend/codehive/api/routes/sessions.py` — endpoint for inter-agent messages

## Communication patterns
- **Query**: orchestrator calls `query_agent(session_id)` → gets last N events + current task + status
- **Message**: agent calls `send_to_agent(session_id, message)` → message appears in target's context
- **Broadcast**: agent calls `broadcast(message)` → message sent to all siblings via parent

## Dependencies
- Depends on: #21 (sub-agent spawning), #07 (event bus), #09 (engine adapter)
