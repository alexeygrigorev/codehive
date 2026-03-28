import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  use: {
    baseURL: "http://localhost:5174",
    headless: true,
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command:
        "cd ../backend && uv run codehive serve --host 127.0.0.1 --port 7444",
      url: "http://127.0.0.1:7444/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: {
        CODEHIVE_DATABASE_URL:
          "sqlite+aiosqlite:////tmp/codehive-e2e-test.db",
        CODEHIVE_PROJECTS_DIR: "/tmp/codehive-e2e",
        CODEHIVE_PORT: "7444",
        CODEHIVE_CORS_ORIGINS: "http://localhost:5174",
      },
    },
    {
      command: "npm run dev -- --port 5174",
      url: "http://localhost:5174",
      reuseExistingServer: !process.env.CI,
      timeout: 15_000,
      env: {
        VITE_API_BASE_URL: "http://localhost:7444",
      },
    },
  ],
});
