# Issue #116: Use separate database for e2e tests

## Problem

Playwright e2e tests create projects, sessions, and messages in the same SQLite database as the real app. This pollutes the user's data with test artifacts (e.g., "e2e-test-project", "e2e-105-project-*", "QA Test Project", etc.) visible in the sidebar and dashboard.

## Requirements

- [ ] E2e tests use a separate/temporary database, not the production one
- [ ] The test database is created fresh for each test run (or cleaned up after)
- [ ] The backend started by Playwright uses a test-specific DATABASE_URL
- [ ] No test data leaks into the user's real database
- [ ] Test cleanup: remove test database after test run completes

## Implementation Ideas

- Set `CODEHIVE_DATABASE_URL=sqlite+aiosqlite:///data/test.db` (or `/tmp/codehive-test.db`) in the Playwright config's `webServer.env`
- Or use an in-memory SQLite database for tests
- The backend already respects `DATABASE_URL` from config — just need to override it for the test server process
- Playwright config at `web/playwright.config.ts` has `webServer` entries where env vars can be set

## Notes

- This should also clean up the sidebar which currently shows dozens of test projects
- Consider adding a `globalSetup` / `globalTeardown` in Playwright to handle database lifecycle
