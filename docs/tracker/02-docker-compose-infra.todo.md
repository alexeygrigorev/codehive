# 02: Docker Compose Infrastructure

## Description
Set up docker-compose with PostgreSQL and Redis for local development.

## Scope
- `docker-compose.yml` at repo root — Postgres 16 + Redis 7
- `backend/codehive/config.py` — Add database URL and Redis URL settings
- Document how to start services in README or Makefile

## Dependencies
- Depends on: #01 (config.py must exist)
