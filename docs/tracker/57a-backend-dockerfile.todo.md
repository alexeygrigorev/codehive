# 57a: Backend Dockerfile + Production Compose

## Description
Create a production Dockerfile for the backend and extend docker-compose.yml to include the backend service alongside postgres and redis.

## Implementation Plan

### 1. Backend Dockerfile
- `backend/Dockerfile`
- Multi-stage build:
  - Stage 1 (builder): `python:3.12-slim`, install `uv`, copy `pyproject.toml` + `uv.lock`, install dependencies
  - Stage 2 (runtime): `python:3.12-slim`, copy installed packages + source code, expose port 8000
- Entrypoint: `uvicorn codehive.api.app:app --host 0.0.0.0 --port 8000`
- Non-root user for security
- Health check: `CMD curl -f http://localhost:8000/api/health || exit 1`

### 2. Production docker-compose
- `docker-compose.prod.yml` (separate from dev compose)
- Services:
  - `backend`: builds from `backend/Dockerfile`, depends on postgres + redis, env vars from `.env`
  - `postgres`: same as dev but with production volume mount
  - `redis`: same as dev
- Environment variables:
  - `DATABASE_URL`, `REDIS_URL`, `CODEHIVE_SECRET_KEY`, `CODEHIVE_LOG_LEVEL`
- Healthchecks for all services
- Restart policy: `unless-stopped`

### 3. Environment documentation
- `docs/deployment.md` -- list all required env vars with descriptions and defaults
- `.env.example` -- template env file

### 4. Alembic migration on startup
- Entrypoint script `backend/docker-entrypoint.sh`:
  1. Run `alembic upgrade head`
  2. Start uvicorn
- Handles first-run DB setup automatically

## Acceptance Criteria

- [ ] `backend/Dockerfile` exists and builds successfully: `docker build -t codehive-backend backend/`
- [ ] Multi-stage build produces a slim image (under 500MB)
- [ ] Backend runs as non-root user inside the container
- [ ] `docker-compose.prod.yml` brings up backend + postgres + redis
- [ ] Backend health check passes: `GET /api/health` returns 200
- [ ] Alembic migrations run automatically on container start
- [ ] `.env.example` documents all required environment variables
- [ ] `docs/deployment.md` exists with setup instructions

## Test Scenarios

### Build: Dockerfile
- `docker build -t codehive-backend backend/` completes without errors
- Container starts and `/api/health` returns 200

### Integration: docker-compose.prod.yml
- `docker compose -f docker-compose.prod.yml up -d` starts all 3 services
- Backend can connect to postgres (health check passes)
- Backend can connect to redis (health check passes)
- `docker compose -f docker-compose.prod.yml down` tears down cleanly

### Environment: Variables
- Start without DATABASE_URL, verify meaningful error message
- Start with all required vars, verify successful startup

## Dependencies
- Depends on: #01 (FastAPI app), #02 (docker-compose infra)
