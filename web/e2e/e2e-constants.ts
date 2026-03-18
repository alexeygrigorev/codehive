/**
 * Shared constants for e2e tests.
 *
 * The backend runs on a dedicated test port (7444) to avoid conflicts with
 * the development server (7433).  Tests that make direct API calls should
 * import API_BASE from here instead of hardcoding a URL.
 */
export const API_BASE =
  process.env.E2E_API_BASE ?? "http://localhost:7444";

/**
 * Path to the test-specific SQLite database.
 * Must match the CODEHIVE_DATABASE_URL configured in playwright.config.ts.
 */
export const TEST_DB_PATH = "/tmp/codehive-e2e-test.db";
