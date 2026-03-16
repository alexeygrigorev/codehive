# 57: Deployment -- Dockerfile + Production Config (Parent)

## Description
Production-ready deployment: Dockerfile for backend, nginx config for frontend, docker-compose for full stack, environment variable documentation, health checks. Split into two sub-issues.

## Sub-Issues
- **57a** -- Backend Dockerfile + production docker-compose (backend, postgres, redis, all in one compose)
- **57b** -- Frontend build + nginx reverse proxy + full-stack compose

## Dependencies
- Depends on: #01 (FastAPI), #02 (docker-compose), #14 (React app)
