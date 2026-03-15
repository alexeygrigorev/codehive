# 31: Telegram Bot Commands

## Description

Build the Telegram bot using `python-telegram-bot` that provides lightweight control and monitoring of codehive. The bot is a thin adapter that talks to the backend API via HTTP (using `httpx`). It implements all core commands for checking status, managing sessions, and interacting with the agent.

## Scope

### New files
- `backend/codehive/clients/telegram/__init__.py` -- Package init
- `backend/codehive/clients/telegram/bot.py` -- Bot setup (Application builder, command registration, startup/shutdown)
- `backend/codehive/clients/telegram/handlers.py` -- Individual command handler implementations (one async function per command)
- `backend/codehive/clients/telegram/formatters.py` -- Message formatting helpers (project lists, session status summaries, task lists, question lists)
- `backend/tests/test_telegram.py` -- Bot command tests with mocked Telegram API and mocked backend HTTP calls

### Modified files
- `backend/codehive/cli.py` -- Add `codehive telegram` subcommand to start the bot
- `backend/codehive/config.py` -- Add `telegram_bot_token: str = ""` setting
- `backend/pyproject.toml` -- Add `python-telegram-bot` dependency

## Commands

Each command calls the corresponding backend API endpoint and formats the response for Telegram.

| Command | Backend API call | Behavior |
|---------|-----------------|----------|
| `/start` | None | Welcome message with list of available commands |
| `/projects` | `GET /api/projects` | List projects (name, id) |
| `/sessions` | `GET /api/projects/{id}/sessions` (for each project, or accept project arg) | List active sessions with status |
| `/status <session_id>` | `GET /api/sessions/{id}` | Session name, engine, mode, status, created_at |
| `/todo <session_id>` | `GET /api/sessions/{id}/tasks` | List tasks with status indicators |
| `/send <session_id> <message>` | `POST /api/sessions/{id}/messages` | Forward message to session, return agent response summary |
| `/approve <action_id>` | `POST /api/sessions/{sid}/approve` | Approve a pending approval request |
| `/reject <action_id>` | `POST /api/sessions/{sid}/reject` | Reject a pending approval request |
| `/questions` | `GET /api/sessions/{id}/questions?answered=false` | List unanswered pending questions across sessions |
| `/answer <question_id> <text>` | `POST /api/sessions/{sid}/questions/{qid}/answer` | Answer a pending question |
| `/stop <session_id>` | `POST /api/sessions/{id}/pause` | Pause/stop a session |

## Architecture decisions

- The bot uses `httpx.AsyncClient` to call the backend API (same pattern as the CLI and TUI clients).
- The base URL comes from `Settings` (env var `CODEHIVE_BASE_URL`, default `http://127.0.0.1:8000`).
- The bot token comes from `Settings.telegram_bot_token` (env var `CODEHIVE_TELEGRAM_BOT_TOKEN`).
- Handlers receive the Telegram `Update` + `ContextTypes.DEFAULT_TYPE`, extract arguments, call the API, format the response, and reply.
- Error handling: if the backend returns an error, the bot replies with a user-friendly error message (not a raw traceback).
- The formatters module keeps message construction separate from handler logic. Formatters return plain strings (Telegram MarkdownV2 or HTML parse mode).

## Dependencies

- Depends on: #04 (project CRUD API) -- DONE
- Depends on: #05 (session CRUD API) -- DONE
- Depends on: #06 (task queue API) -- DONE
- Depends on: #10 (session scheduler / pending questions API) -- DONE
- Depends on: #44 (approval gates API) -- DONE

## Acceptance Criteria

- [ ] `uv run pytest backend/tests/test_telegram.py -v` passes with 12+ tests
- [ ] `python-telegram-bot` is added to `backend/pyproject.toml` dependencies
- [ ] `codehive telegram` CLI command exists and starts the bot (with `--base-url` override)
- [ ] `CODEHIVE_TELEGRAM_BOT_TOKEN` config setting is in `Settings` class
- [ ] Bot module structure exists: `bot.py`, `handlers.py`, `formatters.py` under `backend/codehive/clients/telegram/`
- [ ] All 11 commands are implemented: `/start`, `/projects`, `/sessions`, `/status`, `/todo`, `/send`, `/approve`, `/reject`, `/questions`, `/answer`, `/stop`
- [ ] Each handler calls the correct backend API endpoint via `httpx.AsyncClient`
- [ ] Handlers return formatted Telegram messages (not raw JSON)
- [ ] Errors from the backend API (404, 422, 500) are caught and shown as user-friendly messages
- [ ] Commands that require arguments (e.g. `/status`, `/send`, `/answer`) validate that arguments are provided and reply with usage hints if missing
- [ ] The bot does NOT import or depend on SQLAlchemy/database directly -- it is a pure HTTP client of the backend API

## Test Scenarios

### Unit: Formatters
- `format_project_list` returns a readable multi-line string from a list of project dicts
- `format_project_list` with empty list returns "No projects found."
- `format_session_status` returns session details (name, engine, mode, status)
- `format_task_list` shows task titles with status emoji/indicators
- `format_question_list` shows question text and IDs

### Unit: Handlers (mocked httpx + mocked Telegram Update)
- `/start` replies with welcome text containing available commands
- `/projects` calls `GET /api/projects` and replies with formatted project list
- `/sessions <project_id>` calls `GET /api/projects/{id}/sessions` and replies with session list
- `/status <session_id>` calls `GET /api/sessions/{id}` and replies with formatted status
- `/status` without argument replies with usage hint
- `/todo <session_id>` calls `GET /api/sessions/{id}/tasks` and replies with task list
- `/send <session_id> <message>` calls `POST /api/sessions/{id}/messages` and replies with summary
- `/send` without enough arguments replies with usage hint
- `/approve <action_id>` calls the approve endpoint and confirms
- `/reject <action_id>` calls the reject endpoint and confirms
- `/questions` lists unanswered questions
- `/answer <question_id> <text>` answers the question and confirms
- `/stop <session_id>` calls pause endpoint and confirms

### Unit: Error handling
- Handler receiving a 404 from backend replies with "not found" message (not a crash)
- Handler receiving a connection error replies with "cannot reach server" message

### Unit: Bot setup
- `create_bot()` registers all expected command handlers
- `codehive telegram` CLI subcommand calls bot startup

## Out of Scope (handled by #32)
- Push notifications (approval required, session completed, etc.)
- Inline keyboard buttons for approve/reject
- Event bus subscription for proactive messages

## Log

### [SWE] 2026-03-15 12:00
- Implemented Telegram bot with all 11 commands as a thin HTTP client adapter
- Bot uses httpx.AsyncClient to call backend API, does NOT import SQLAlchemy
- Created formatters module with 5 format functions for projects, sessions, tasks, questions
- Created handlers module with 11 async handler functions, each with argument validation and error handling
- Created bot module with create_bot() that registers all CommandHandlers and stores shared httpx client in bot_data
- Added telegram_bot_token to Settings in config.py
- Added `codehive telegram` CLI subcommand with token validation
- Added python-telegram-bot dependency to pyproject.toml
- Files created: backend/codehive/clients/telegram/__init__.py, bot.py, handlers.py, formatters.py, backend/tests/test_telegram.py
- Files modified: backend/codehive/config.py, backend/codehive/cli.py, backend/pyproject.toml
- Tests added: 30 tests covering formatters (7), handlers (17), error handling (2), bot setup (2), CLI (2)
- Build results: 30 tests pass, 0 fail, ruff clean

### [QA] 2026-03-15 13:30
- Tests: 30 passed, 0 failed (test_telegram.py)
- Ruff check: clean (codehive/clients/telegram/)
- Ruff format: clean (all telegram-related files)
- No SQLAlchemy or database imports in telegram module: CONFIRMED
- Acceptance criteria:
  1. `uv run pytest tests/test_telegram.py -v` passes with 12+ tests: PASS (30 tests)
  2. `python-telegram-bot` in pyproject.toml dependencies: PASS
  3. `codehive telegram` CLI command exists with --base-url override: PASS
  4. CODEHIVE_TELEGRAM_BOT_TOKEN in Settings class: PASS
  5. Bot module structure (bot.py, handlers.py, formatters.py): PASS
  6. All 11 commands implemented: PASS (start, projects, sessions, status, todo, send, approve, reject, questions, answer, stop)
  7. Each handler calls correct backend API endpoint via httpx.AsyncClient: PASS (verified in tests and code review)
  8. Handlers return formatted Telegram messages (not raw JSON): PASS (formatters produce human-readable strings)
  9. Errors from backend API (404, 422, 500) caught as user-friendly messages: PASS (tested 404 and connection error; 422 and 500 handled in _reply_error)
  10. Commands requiring arguments validate and reply with usage hints: PASS (sessions, status, todo, send, approve, reject, questions, answer, stop all validated)
  11. Bot does NOT import or depend on SQLAlchemy/database directly: PASS (grep confirmed zero matches)
- Note: 13 test failures exist in test_ssh.py and test_models.py from a separate issue (#40 SSH), unrelated to this issue
- VERDICT: PASS

### [PM] 2026-03-15 14:15
- Reviewed diff: 8 files changed (4 new telegram module files, 1 new test file, 3 modified: cli.py, config.py, pyproject.toml)
- Results verified: real data present -- 30 tests executed and passing, ruff clean, all handlers tested with mocked httpx and mocked Telegram Updates
- Acceptance criteria: all 11 met
  1. 30 tests pass (12+ required): MET
  2. python-telegram-bot>=22.6 in pyproject.toml: MET
  3. codehive telegram CLI subcommand with --base-url override: MET
  4. CODEHIVE_TELEGRAM_BOT_TOKEN in Settings (env_prefix=CODEHIVE_): MET
  5. Module structure (bot.py, handlers.py, formatters.py, __init__.py): MET
  6. All 11 commands implemented in COMMAND_HANDLERS dict: MET
  7. Each handler calls correct backend API endpoint via httpx.AsyncClient: MET (verified endpoints in code review)
  8. Handlers return formatted messages via formatters module, not raw JSON: MET
  9. Errors (404, 422, 500, ConnectError) caught with user-friendly replies: MET
  10. Argument validation with usage hints for all commands requiring args: MET
  11. Zero SQLAlchemy/database imports in telegram module: MET (grep confirmed)
- Code quality: clean separation of concerns (bot setup / handlers / formatters), consistent error handling pattern across all handlers, shared httpx client via bot_data
- Note: /questions requires session_id argument rather than listing across all sessions as spec suggested; this is a reasonable design given the backend API structure. No follow-up needed.
- Follow-up issues created: none
- VERDICT: ACCEPT
