# 61: Action on Tasks End

## Description
From GitHub issue alexeygrigorev/codehive#1: What to do when tasks end — continue with creating more tasks, or stop if evening is done.

The scheduler (#10) currently just sets session to `idle` when ToDo is empty. This adds configurable behavior: auto-generate next tasks from the issue, stop session, or ask the user.

## Scope
- `backend/codehive/core/scheduler.py` — add on_queue_empty behavior
- `backend/codehive/core/session.py` — add session config for queue_empty_action
- `backend/codehive/api/schemas/session.py` — add config field

## Behavior options
- `stop` — session goes idle, waits for user input (current default)
- `continue` — agent analyzes the issue and generates new tasks, then continues
- `ask` — emit a pending question "Tasks are done. Should I continue or stop?"

## Dependencies
- Depends on: #10 (scheduler), #09 (engine adapter)
