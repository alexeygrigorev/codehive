# 13: Secrets Management

## Description
Keep it simple: `.env` file for all secrets, `.gitignore` to prevent committing. Already done for the most part — just need to make sure config.py loads from `.env` and `.env.example` stays up to date.

## Scope
- `.env` at repo root — all secrets (API keys, DB URL, Redis URL)
- `.env.example` — template without real values
- `.gitignore` — already ignores `.env`
- `backend/codehive/config.py` — Settings loads from `.env` via pydantic-settings
- No encryption, no vault, no DB-stored secrets for now

## Decision
Simplest approach: `.env` + `.gitignore`. Revisit if/when multi-user or deployment needs arise.

## Dependencies
- Depends on: #01 (config.py must exist)
