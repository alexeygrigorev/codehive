# Codehive

Persistent AI coding agent workspace with sub-agent orchestration. Agents live in projects, execute tasks autonomously, create sub-agents, and are accessible from web, mobile, Telegram, and terminal. Not a chat -- an operating system for agent sessions.

## How It Works

Codehive is a self-hosted tool that runs on your own server or computer. There is no hosted version -- you own your instance entirely.

1. Install codehive on your server (or laptop, or home machine)
2. SSH in and run `codehive serve` to start the backend
3. Connect from your clients via SSH port forwarding:
   ```bash
   ssh -L 7433:localhost:7433 yourserver
   ```
4. Open `http://localhost:7433` in your browser, or point the mobile app at it

One user, one instance. Your code and agent data never leave your machine. The backend only listens on `127.0.0.1` — remote access is handled by SSH tunnels on the client side, not by the backend.

## Architecture

Monorepo with three top-level directories:

```
backend/    Python 3.13, FastAPI, SQLAlchemy, Redis
web/        React 19, Vite, TypeScript, Tailwind CSS
mobile/     (planned)
```

Infrastructure (PostgreSQL, Redis) is defined in `docker-compose.yml` at the repo root.

## Prerequisites

- Python 3.13+
- Node.js 20+
- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Git

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd codehive

# 2. Copy environment config
cp .env.example .env
# Edit .env with your values (see Environment Variables below)

# 3. Start infrastructure (PostgreSQL + Redis)
docker compose up -d

# 4. Install backend dependencies and start the API server
cd backend
uv sync --dev
uv run codehive serve

# 5. In another terminal, start the web dev server
cd web
npm install
npm run dev
```

The API server runs at `http://127.0.0.1:7433` and the web app at `http://localhost:5173`.

### Default Login

On first run the server creates an admin user. Credentials are controlled by environment variables:

| Variable | Default |
|---|---|
| `CODEHIVE_ADMIN_USERNAME` | `admin` |
| `CODEHIVE_ADMIN_PASSWORD` | random (printed to server logs) |

Set `CODEHIVE_ADMIN_PASSWORD=admin` in your `.env` for a known password. If the admin was already created and you forgot the password, reset the DB:

```bash
docker exec codehive-postgres-1 psql -U codehive -d codehive \
  -c "DELETE FROM workspace_members; DELETE FROM users; DELETE FROM workspaces;"
```

Then restart `uv run codehive serve` — it will re-seed with your configured credentials.

## Backend

```bash
cd backend
uv sync --dev          # Install dependencies
uv run codehive serve  # Start the API server
```

Options:

```
--host HOST    Bind address (default: 127.0.0.1)
--port PORT    Bind port (default: 7433)
--reload       Enable auto-reload for development
```

The server can also be configured via environment variables (see below).

### Database Migrations

```bash
cd backend
uv run alembic upgrade head    # Apply migrations
uv run alembic revision -m "description" --autogenerate  # Create a new migration
```

## Web App

```bash
cd web
npm install        # Install dependencies
npm run dev        # Start dev server (http://localhost:5173)
npm run build      # Production build
npm run preview    # Preview production build
npm run lint       # Run ESLint
```

## TUI (Terminal Interface)

Interactive terminal dashboard, designed to work over SSH and on small screens.

```bash
cd backend
uv run codehive tui       # Full interactive dashboard
uv run codehive rescue    # Rescue mode (emergency controls)
```

Rescue mode provides emergency access to stop runaway sessions, kill agents, rollback checkpoints, and toggle maintenance mode.

## Telegram Bot

Lightweight client for monitoring sessions, answering questions, and approving actions.

```bash
# Set the bot token
export CODEHIVE_TELEGRAM_BOT_TOKEN=your-token-here

cd backend
uv run codehive telegram
```

Create a bot via [@BotFather](https://t.me/BotFather) on Telegram to get your token.

## CLI Commands

All commands are available via `codehive` (or `uv run codehive` from the `backend/` directory).

| Command | Description |
|---|---|
| `codehive code [directory]` | Start a lightweight coding agent session |
| `codehive serve` | Start the API server |
| `codehive tui` | Launch interactive terminal dashboard |
| `codehive rescue` | Launch rescue mode (emergency TUI) |
| `codehive telegram` | Start the Telegram bot |
| `codehive projects list` | List all projects |
| `codehive projects create NAME --workspace ID` | Create a project |
| `codehive sessions list --project ID` | List sessions for a project |
| `codehive sessions create PROJECT_ID --name NAME` | Create a session |
| `codehive sessions status SESSION_ID` | Show session details |
| `codehive sessions chat SESSION_ID` | Interactive chat with a session |
| `codehive sessions pause SESSION_ID` | Pause a session |
| `codehive sessions rollback SESSION_ID --checkpoint ID` | Rollback to checkpoint |
| `codehive questions list` | List pending questions |
| `codehive questions answer QUESTION_ID "answer"` | Answer a question |
| `codehive system health` | Show system health status |
| `codehive system maintenance on\|off` | Toggle maintenance mode |

Use `--base-url URL` on any command to point at a different server (default: `http://127.0.0.1:7433`). This can also be set via `CODEHIVE_BASE_URL`.

## Running Tests

### Backend

```bash
cd backend
uv run pytest tests/ -v            # Run all tests
uv run pytest --cov=codehive --cov-report=term-missing  # With coverage
uv run ruff check                  # Lint
uv run ruff format --check         # Check formatting
```

### Web

```bash
cd web
npx vitest          # Run tests
npm run lint        # Lint
```

## Environment Variables

Copy `.env.example` to `.env` and fill in your values. DB and Redis defaults match `docker-compose.yml` — no changes needed for local dev.

```bash
CODEHIVE_HOST=127.0.0.1          # API bind address
CODEHIVE_PORT=7433               # API bind port
CODEHIVE_DEBUG=false             # Auto-reload
CODEHIVE_DATABASE_URL=postgresql+asyncpg://codehive:codehive@localhost:5432/codehive
CODEHIVE_REDIS_URL=redis://localhost:6379/0
CODEHIVE_ANTHROPIC_API_KEY=      # Required for native agent engine
CODEHIVE_ANTHROPIC_BASE_URL=     # Optional custom API URL
CODEHIVE_TELEGRAM_BOT_TOKEN=     # For `codehive telegram`
CODEHIVE_TELEGRAM_CHAT_ID=       # For Telegram notifications
CODEHIVE_GITHUB_DEFAULT_TOKEN=   # For GitHub integration
```

## Infrastructure

Start and stop PostgreSQL and Redis via Docker Compose:

```bash
docker compose up -d       # Start
docker compose down        # Stop
docker compose ps          # Status
```

Or from the backend directory using Make:

```bash
cd backend
make infra-up       # Start
make infra-down     # Stop
make infra-status   # Status
```

## License

WTFPL
