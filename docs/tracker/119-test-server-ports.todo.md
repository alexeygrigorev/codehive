# Issue #119: E2e tests should use different ports from dev servers

## Problem

Playwright e2e tests start backend on port 7433 and frontend on port 5173 — the same ports as the dev servers. If the user is running `codehive dev` while tests run, they conflict and either the tests fail or the dev servers get killed.

## Requirements

- [ ] E2e tests use separate ports (e.g., backend 7434, frontend 5174)
- [ ] Playwright config (`web/playwright.config.ts`) sets test-specific ports for both webServer entries
- [ ] Frontend's API base URL points to the test backend port
- [ ] All e2e test files use the test ports, not hardcoded 7433/5173
- [ ] Dev servers on 7433/5173 are unaffected by test runs

## Notes

- Combine with #116 (separate test database) for full test isolation
- The Playwright `webServer` config supports `port` and `env` overrides
- Frontend API base URL is configured via VITE_API_BASE_URL or similar
