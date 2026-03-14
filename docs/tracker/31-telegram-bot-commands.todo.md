# 31: Telegram Bot Commands

## Description
Build the Telegram bot using python-telegram-bot that provides lightweight control and monitoring of codehive. Implement all core commands for checking status, managing sessions, and interacting with the agent.

## Scope
- `backend/codehive/clients/telegram/bot.py` -- Bot setup, command handlers, conversation flow
- `backend/codehive/clients/telegram/handlers.py` -- Individual command handler implementations
- `backend/codehive/clients/telegram/formatters.py` -- Message formatting helpers (status summaries, session info)
- `backend/codehive/cli.py` -- Add `codehive telegram` command to start the bot
- `backend/tests/test_telegram.py` -- Bot command tests (with mocked Telegram API)

## Commands
- `/projects` -- List projects
- `/sessions` -- List active sessions
- `/status <session>` -- Session status and progress
- `/todo <session>` -- View/add ToDo items
- `/send <session> <message>` -- Send message to session
- `/approve <id>` -- Approve pending action
- `/reject <id>` -- Reject pending action
- `/questions` -- List pending questions
- `/answer <id> <text>` -- Answer a question
- `/stop <session>` -- Stop session

## Dependencies
- Depends on: #04 (project CRUD API)
- Depends on: #05 (session CRUD API)
- Depends on: #06 (task queue API)
- Depends on: #10 (pending questions API)
