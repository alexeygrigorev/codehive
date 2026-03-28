# 145 — Task creation from conversation: chat → backlog

## Problem
Currently the user creates tasks by writing markdown files or telling the orchestrator in natural language. There's no smooth way to go from "the sidebar is broken" in a chat to a well-formed task in the backlog.

## Vision
The user chats with the orchestrator session. When they describe a problem or feature, the orchestrator creates a task via the API:
- Extracts title and description from the conversation
- Creates the task in the backlog
- The pipeline picks it up automatically

## What this looks like
- A `create_task` tool available to the orchestrator session
- The tool takes title, description, and optional acceptance criteria
- The task appears in the backlog immediately
- The pipeline web UI shows it and the orchestrator picks it up

## Acceptance criteria
- [ ] `create_task` tool available in orchestrator sessions
- [ ] Tool creates a task in the backlog via the API
- [ ] Task appears in the pipeline UI immediately
- [ ] Orchestrator can create tasks from natural language descriptions
- [ ] Created tasks have title, description, and optional acceptance criteria
