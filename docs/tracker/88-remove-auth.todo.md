# Issue #88: Remove authentication / make it optional

## Problem

The app has a full JWT auth system (login, access/refresh tokens, password hashing, role-based permissions) but this is a self-hosted single-user tool. Auth adds friction (login screen, token management) with no real benefit for the primary use case.

## Requirements

- [ ] Remove the login screen from the web frontend — go straight to the dashboard
- [ ] Make auth middleware optional / disabled by default
- [ ] Remove or skip JWT token checks on API routes when auth is disabled
- [ ] Remove the first-run admin user seeding (or make it no-op when auth is off)
- [ ] Keep the auth code in place but behind a `CODEHIVE_AUTH_ENABLED=false` (default false) setting so it can be re-enabled later if needed
- [ ] WebSocket connections should work without token when auth is disabled
- [ ] Mobile app should skip the login screen when auth is disabled

## Notes

- Don't delete the auth code — just bypass it with a config flag
- The web app's API client should stop sending Authorization headers when auth is off
- The `/api/auth/login` endpoint can remain but is unused when auth is disabled
