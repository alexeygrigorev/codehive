# 30: Terminal Client - Rescue Mode

## Description
Implement a minimal rescue mode for the terminal client, designed for phone-over-SSH emergencies. Shows failed sessions, pending questions, system health, and provides one-command actions: stop, rollback, restart, answer.

## Scope
- `backend/codehive/clients/terminal/screens/rescue.py` -- Rescue mode screen: failed sessions, pending questions, system health
- `backend/codehive/cli.py` -- Add `codehive rescue` command that launches rescue screen directly
- `backend/tests/test_rescue.py` -- Rescue mode tests

## Behavior
- `codehive rescue` launches directly into rescue mode (no dashboard navigation needed)
- Shows: failed/stuck sessions, unanswered questions, system health summary
- One-key actions: stop session, rollback checkpoint, restart session, answer question
- Designed for small screens and minimal keyboard input

## Dependencies
- Depends on: #27 (TUI app shell)
- Depends on: #24 (checkpoint rollback)
- Depends on: #10 (pending questions)
