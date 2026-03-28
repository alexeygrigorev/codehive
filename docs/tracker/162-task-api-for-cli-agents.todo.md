# 162 — Task API for CLI agents: fetch and update assigned tasks

## Problem
CLI-based agents (Claude Code, Codex, Copilot, Gemini) can't use custom tools — they only have their built-in tool sets. They need a way to:
1. Fetch their assigned task details (acceptance criteria, description)
2. Report progress (write log entries)
3. Submit verdicts (pass/fail)

Since we can't inject tools into these CLIs, they need an HTTP API they can call directly.

## Vision
A simple REST API that agents can call from their environment:
- `GET /api/agent/my-task` — returns the task assigned to the current session (looked up by session ID passed as header/query)
- `POST /api/agent/log` — append a log entry to the assigned task
- `POST /api/agent/verdict` — submit a structured verdict

The orchestrator passes the API URL and session ID to the agent's initial prompt, so the agent knows how to call back.

## What this looks like
In the agent's system prompt:
```
You are working on task "Fix sidebar scroll".
Task API: http://localhost:7433/api/agent
Session ID: abc-123

To read your task: curl $TASK_API/my-task -H "X-Session-Id: $SESSION_ID"
To log progress: curl -X POST $TASK_API/log -H "X-Session-Id: $SESSION_ID" -d '{"content": "..."}'
To submit verdict: curl -X POST $TASK_API/verdict -H "X-Session-Id: $SESSION_ID" -d '{"verdict": "PASS"}'
```

## Acceptance criteria
- [ ] GET /api/agent/my-task returns task details for the session's bound task
- [ ] POST /api/agent/log appends log entry to the bound task
- [ ] POST /api/agent/verdict submits structured verdict for the session
- [ ] Session ID passed via X-Session-Id header
- [ ] Returns 404 if session has no bound task
- [ ] Orchestrator includes API URL and session ID in agent instructions
- [ ] Works for any CLI engine (no custom tools required)
