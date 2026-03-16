# 57b: Frontend Build + Nginx Reverse Proxy

## Description
Build the React frontend for production, serve it via nginx, and configure nginx as a reverse proxy to the backend API. Add to docker-compose.prod.yml.

## Implementation Plan

### 1. Frontend Dockerfile
- `web/Dockerfile`
- Multi-stage build:
  - Stage 1 (builder): `node:20-alpine`, install dependencies, `npm run build`
  - Stage 2 (runtime): `nginx:alpine`, copy built files to `/usr/share/nginx/html`, copy nginx config

### 2. Nginx config
- `web/nginx.conf`
- Serves frontend static files from `/`
- Reverse proxy `/api/` to `http://backend:7433/api/`
- Reverse proxy `/ws/` to `http://backend:7433/ws/` with WebSocket upgrade headers
- SPA fallback: all non-API, non-static routes serve `index.html`
- Gzip compression enabled
- Security headers: `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`

### 3. Update docker-compose.prod.yml
- Add `frontend` service:
  - Builds from `web/Dockerfile`
  - Depends on `backend`
  - Exposes port 80 (and optionally 443)
  - Maps to host port 80

### 4. Frontend environment
- `web/.env.production` -- set `VITE_API_URL` to empty (nginx proxies)
- Build-time vs runtime config: API URL is relative when behind nginx

## Acceptance Criteria

- [ ] `web/Dockerfile` exists and builds successfully: `docker build -t codehive-frontend web/`
- [ ] Frontend build produces static files in `/usr/share/nginx/html`
- [ ] Nginx serves the React app on `/`
- [ ] Nginx proxies `/api/*` requests to the backend
- [ ] Nginx proxies `/ws/*` WebSocket connections to the backend
- [ ] SPA routing works: navigating to `/projects/123` serves `index.html`
- [ ] Full stack starts with `docker compose -f docker-compose.prod.yml up -d`
- [ ] Browsing to `http://localhost` shows the codehive web app

## Test Scenarios

### Build: Frontend Dockerfile
- `docker build -t codehive-frontend web/` completes without errors
- Built image contains `index.html` in nginx html directory

### Integration: Nginx proxy
- Start full stack, verify `http://localhost/api/health` returns 200 (proxied to backend)
- Verify `http://localhost/` returns the React app HTML
- Verify `http://localhost/projects` returns `index.html` (SPA fallback)

### Integration: WebSocket
- Start full stack, connect WebSocket to `ws://localhost/ws/events`
- Verify connection is established through nginx

### Security: Headers
- GET `/`, verify `X-Frame-Options` header is present
- Verify `X-Content-Type-Options: nosniff` header is present

## Dependencies
- Depends on: #57a (backend Dockerfile + compose), #14 (React app)
