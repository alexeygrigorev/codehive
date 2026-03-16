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

## Log

### [SWE] 2026-03-16 10:00
- Rewrote README.md with all 11 required sections
- Sections included: What is Codehive, Architecture, Prerequisites, Quick Start, Backend, Web App, TUI, Telegram Bot, CLI Commands (full table), Running Tests (backend + web), Environment Variables (full table from config.py and .env.example)
- Also added Infrastructure section (docker compose and make targets) and License
- All content derived from actual codebase: cli.py, config.py, pyproject.toml, docker-compose.yml, .env.example, web/package.json, backend/Makefile
- Files modified: README.md
- Tests: N/A (documentation-only issue)
- Build: N/A
- Known limitations: none
