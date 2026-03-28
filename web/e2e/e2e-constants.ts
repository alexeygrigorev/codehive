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

/**
 * Temporary base directory for e2e test project files.
 * All e2e tests that create project directories should use this path
 * instead of the user's home directory.  Cleaned up by global-teardown.ts.
 */
export const E2E_TEMP_DIR = "/tmp/codehive-e2e";
