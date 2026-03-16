# 63: README — How to Run

## Description
Update README.md with instructions for running codehive: backend, web app, TUI, Telegram bot, and development setup.

## Scope
- `README.md` — rewrite with getting started, architecture overview, running instructions

## Sections needed
1. **What is Codehive** — one-paragraph description
2. **Architecture** — monorepo structure (backend/, web/, mobile/)
3. **Prerequisites** — Python 3.13, Node 20, Docker, uv, git
4. **Quick Start** — docker-compose up, backend serve, web dev server
5. **Backend** — `cd backend && uv sync --dev && uv run codehive serve`
6. **Web App** — `cd web && npm install && npm run dev`
7. **TUI** — `codehive tui` and `codehive rescue`
8. **Telegram Bot** — `codehive telegram` with token setup
9. **CLI** — list of available commands
10. **Running Tests** — backend pytest, frontend vitest
11. **Environment Variables** — reference to .env.example

## Dependencies
- None (documentation only)
