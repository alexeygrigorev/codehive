# 29: CLI Command Mode (Extended)

## Description
Extend the CLI with all non-interactive commands for scripting, automation, and emergency use. These commands go beyond the basic session commands in #11 to cover the full operational surface.

## Scope
- `backend/codehive/cli.py` -- Extend with additional subcommands
- `backend/tests/test_cli_commands.py` -- CLI command tests

## Commands
- `codehive session pause <id>` -- Pause a running session
- `codehive session rollback <id> --checkpoint <cp_id>` -- Rollback to checkpoint
- `codehive questions list` -- List all pending questions across sessions
- `codehive questions answer <id> "<answer>"` -- Answer a pending question
- `codehive system health` -- Show system health (DB, Redis, active sessions)
- `codehive system maintenance on|off` -- Enable/disable maintenance mode

## Dependencies
- Depends on: #11 (basic CLI session commands)
- Depends on: #24 (checkpoint rollback)
- Depends on: #10 (pending questions API)
