# 11: CLI Session Commands

## Description
Add CLI commands for creating sessions and chatting with them interactively from the terminal.

## Scope
- `backend/codehive/cli.py` — Extend with session subcommands
- `backend/tests/test_cli.py` — CLI tests

## Commands
- `codehive projects list` — list all projects
- `codehive projects create <name> <path>` — create a project
- `codehive sessions list --project <id>` — list sessions for a project
- `codehive sessions create <project_id> --name <name>` — create a session
- `codehive sessions chat <session_id>` — interactive chat with a session (stdin/stdout)
- `codehive sessions status <session_id>` — show session status, current task, pending questions

## Dependencies
- Depends on: #09 (needs engine to chat), #04 (project CRUD), #05 (session CRUD)
