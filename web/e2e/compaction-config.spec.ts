import { test, expect, type Page, type APIRequestContext } from "@playwright/test";
import { API_BASE, TEST_DB_PATH } from "./e2e-constants";

/**
 * Helper: Create a project and session via API, returning the session ID.
 */
async function createProjectAndSession(
  request: APIRequestContext,
  suffix: string,
): Promise<{ projectId: string; sessionId: string }> {
  const projResp = await request.post(`${API_BASE}/api/projects`, {
    data: { name: `e2e-compact-${suffix}`, path: `/tmp/e2e-compact-${suffix}` },
  });
  expect(projResp.ok()).toBeTruthy();
  const project = await projResp.json();

  const sessResp = await request.post(
    `${API_BASE}/api/projects/${project.id}/sessions`,
    { data: { name: `compact-session-${suffix}`, engine: "native", mode: "execution" } },
  );
  expect(sessResp.ok()).toBeTruthy();
  const session = await sessResp.json();

  return { projectId: project.id, sessionId: session.id };
}

/**
 * Helper: Navigate to a session page and click the Compaction sidebar tab.
 */
async function navigateToCompactionTab(page: Page, sessionId: string): Promise<void> {
  await page.goto(`/sessions/${sessionId}`);
  // Wait for session header
  const header = page.getByTestId("session-header");
  await expect(header).toBeVisible({ timeout: 10_000 });

  // Wait for sidebar to appear
  const sidebar = page.getByTestId("session-sidebar");
  await expect(sidebar).toBeVisible({ timeout: 10_000 });

  // Click the "Compaction" tab
  const compactionTab = sidebar.locator('button[role="tab"]', { hasText: "Compaction" });
  await expect(compactionTab).toBeVisible();
  await compactionTab.click();

  // Wait for the compaction panel to appear
  await expect(page.getByTestId("compaction-panel")).toBeVisible({ timeout: 5_000 });
}

/**
 * Helper: Insert a context.compacted event directly into the database via
 * SQLite. Since there is no POST /events API, we use the backend's SQLite
 * database directly.
 */
async function seedCompactionEvent(
  request: APIRequestContext,
  sessionId: string,
  data: Record<string, unknown>,
): Promise<void> {
  // Since there is no POST /events API, insert directly into the SQLite DB.
  const { execSync } = await import("child_process");
  const { randomUUID } = await import("crypto");

  const eventId = randomUUID();
  const now = new Date().toISOString();
  const jsonData = JSON.stringify(data).replace(/'/g, "''");

  // Use the test-specific database (matches CODEHIVE_DATABASE_URL in playwright.config.ts)
  const dbPath = TEST_DB_PATH;
  const sql = `INSERT INTO events (id, session_id, type, data, created_at) VALUES ('${eventId}', '${sessionId}', 'context.compacted', '${jsonData}', '${now}');`;

  // Pipe SQL via stdin to avoid shell quoting issues with JSON double-quotes
  execSync(`sqlite3 "${dbPath}"`, { input: sql });
}

test.describe("Compaction configuration UI", () => {
  test("E2E 1: Compaction settings controls render and persist", async ({
    page,
    request,
  }) => {
    const { sessionId } = await createProjectAndSession(
      request,
      `settings-${Date.now()}`,
    );

    // 1-2. Navigate to session and click Compaction tab
    await navigateToCompactionTab(page, sessionId);

    // 3. Assert: toggle "Auto-compaction" is ON (checked)
    const toggle = page.getByTestId("compaction-toggle");
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute("aria-checked", "true");

    // 4. Assert: threshold slider shows 80%
    const thresholdValue = page.getByTestId("threshold-value");
    await expect(thresholdValue).toHaveText("80%");

    // 5. Assert: keep-recent stepper shows 4
    const keepRecentValue = page.getByTestId("keep-recent-value");
    await expect(keepRecentValue).toHaveText("4");

    // 6. Toggle auto-compaction OFF
    await toggle.click();

    // 7. Wait for network request to complete (PATCH /api/sessions/:id)
    await page.waitForResponse(
      (resp) =>
        resp.url().includes(`/api/sessions/${sessionId}`) &&
        resp.request().method() === "PATCH",
    );

    // 8. Reload the page
    await page.reload();

    // 9. Click the Compaction tab again
    const sidebar = page.getByTestId("session-sidebar");
    await expect(sidebar).toBeVisible({ timeout: 10_000 });
    const compactionTab = sidebar.locator('button[role="tab"]', {
      hasText: "Compaction",
    });
    await compactionTab.click();
    await expect(page.getByTestId("compaction-panel")).toBeVisible({
      timeout: 5_000,
    });

    // 10. Assert: toggle is OFF
    const toggleAfterReload = page.getByTestId("compaction-toggle");
    await expect(toggleAfterReload).toHaveAttribute("aria-checked", "false");

    // 11. Assert: threshold is still 80%, keep-recent is still 4
    await expect(page.getByTestId("threshold-value")).toHaveText("80%");
    await expect(page.getByTestId("keep-recent-value")).toHaveText("4");

    await page.screenshot({
      path: "/tmp/e2e-compaction-settings.png",
      fullPage: true,
    });
  });

  test("E2E 2: Compaction history displays past compactions", async ({
    page,
    request,
  }) => {
    const { sessionId } = await createProjectAndSession(
      request,
      `history-${Date.now()}`,
    );

    // Seed a compaction event into the database
    await seedCompactionEvent(request, sessionId, {
      messages_compacted: 12,
      messages_preserved: 4,
      summary_text:
        "Summary of conversation about authentication flow and session management with detailed discussion of token handling",
      threshold_percent: 82.3,
    });

    // 1-2. Navigate to session and click Compaction tab
    await navigateToCompactionTab(page, sessionId);

    // 3. Assert: "Compaction History" section is visible
    await expect(page.locator("text=Compaction History")).toBeVisible();

    // 4. Assert: at least one compaction entry is displayed
    const entries = page.getByTestId("compaction-history-entry");
    await expect(entries.first()).toBeVisible({ timeout: 5_000 });

    // 5. Assert: the entry shows messages compacted count (12)
    await expect(entries.first()).toContainText("12 compacted");

    // 6. Click the entry to expand
    await entries.first().click();

    // 7. Assert: full summary text is visible in the expanded section
    const expanded = page.getByTestId("compaction-history-expanded");
    await expect(expanded).toBeVisible();
    await expect(expanded).toContainText("Messages compacted: 12");
    await expect(expanded).toContainText("Messages preserved: 4");
    await expect(expanded).toContainText("authentication flow");

    // 8. Click again to collapse
    await entries.first().click();

    // 9. Assert: summary text (expanded section) is hidden
    await expect(page.getByTestId("compaction-history-expanded")).not.toBeVisible();

    await page.screenshot({
      path: "/tmp/e2e-compaction-history.png",
      fullPage: true,
    });
  });

  test("E2E 3: Compaction notification appears in chat", async ({
    page,
    request,
  }) => {
    const { sessionId } = await createProjectAndSession(
      request,
      `notify-${Date.now()}`,
    );

    // 2. Seed a context.compacted event into the DB before navigating.
    //    The ChatPanel fetches events on mount (including context.compacted),
    //    so the compaction event will render as a system message on page load.
    await seedCompactionEvent(request, sessionId, {
      messages_compacted: 8,
      messages_preserved: 4,
      summary_text: "Compacted conversation context",
      threshold_percent: 80.0,
    });

    // 1. Navigate to the session page
    await page.goto(`/sessions/${sessionId}`);
    const header = page.getByTestId("session-header");
    await expect(header).toBeVisible({ timeout: 10_000 });

    // Wait for chat panel to be visible
    await expect(page.locator(".chat-panel")).toBeVisible({ timeout: 10_000 });

    // 3. Assert: a system-style message appears containing "Context compacted"
    const compactMessage = page.locator("text=Context compacted");
    await expect(compactMessage).toBeVisible({ timeout: 10_000 });

    // 4. Assert: message contains the counts
    const chatPanel = page.locator(".chat-panel");
    await expect(chatPanel).toContainText("8 messages summarized");
    await expect(chatPanel).toContainText("4 preserved");

    await page.screenshot({
      path: "/tmp/e2e-compaction-notification.png",
      fullPage: true,
    });
  });
});
