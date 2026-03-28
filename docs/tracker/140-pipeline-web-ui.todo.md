# 140 — Pipeline web UI: kanban board with live agent status

## Problem
There's no way to see the pipeline status in the web app. The user can't tell which tasks are being worked on, which agents are active, or where things are stuck.

## Vision
A pipeline dashboard that shows:
- Kanban columns: Backlog → Grooming → Ready → Implementing → Testing → Accepting → Done
- Each task card shows: title, assigned agent, time in stage
- Active agents show a live indicator (spinning, streaming output)
- Click a task to see its full log (all agent entries)
- Click an agent to see its live session output
- "Add Task" button to drop new tasks into the backlog

## What this looks like
- `/pipeline` route showing the kanban board
- Real-time updates via WebSocket/SSE as tasks move through stages
- Task cards are draggable (for manual override if needed)
- Agent status indicators: idle, working, stuck, completed
- Batch grouping: show which tasks are in the same batch

## Acceptance criteria
- [ ] Pipeline page with kanban columns for each stage
- [ ] Tasks appear in the correct column based on status
- [ ] Live updates when tasks move between stages
- [ ] Agent status indicators on active tasks
- [ ] Task detail view with full log
- [ ] Add task button/form
- [ ] Responsive layout
