import { test, expect } from "@playwright/test";

/**
 * Helper: Create a project and session, navigate to the chat panel.
 * Returns when the chat panel is visible and ready for input.
 */
async function setupSession(page: import("@playwright/test").Page) {
  // Navigate to dashboard
  await page.goto("/");
  await expect(page.locator("h1", { hasText: "Dashboard" })).toBeVisible();

  // Create a new project
  await page.click('a:has-text("New Project")');
  await expect(page.locator("h1", { hasText: "New Project" })).toBeVisible();
  await page.click('button:has-text("Empty Project")');

  const projectDir = `/tmp/e2e-106-project-${Date.now()}`;
  await page.fill("#dir-path", projectDir);
  await page.click('button:has-text("Create Project")');

  // Wait for project page
  await expect(page.locator("h1").first()).toBeVisible({ timeout: 10_000 });

  // Create a new session
  await page.click('button:has-text("+ New Session")');

  // Wait for chat panel
  await expect(page.locator(".chat-panel")).toBeVisible({ timeout: 10_000 });
}

test.describe("Optimistic user message rendering", () => {
  test.beforeAll(() => {
    const hasApiKey = !!(
      process.env.CODEHIVE_ANTHROPIC_API_KEY || process.env.ANTHROPIC_API_KEY
    );
    expect(
      hasApiKey,
      "CODEHIVE_ANTHROPIC_API_KEY must be set to run e2e tests",
    ).toBe(true);
  });

  test("E2E Test 1: Optimistic message appears immediately (no 'No messages yet' flash)", async ({
    page,
  }) => {
    await setupSession(page);

    const chatInput = page.locator('textarea[aria-label="Message input"]');
    await expect(chatInput).toBeVisible();

    // Verify empty state placeholder is visible
    await expect(
      page.locator("text=No messages yet. Start the conversation."),
    ).toBeVisible();

    // Type and send a message
    await chatInput.fill("Hello optimistic");
    await chatInput.press("Enter");

    // Immediately check for the user message bubble (within 500ms, no waitForTimeout)
    const userMessage = page.locator('[data-role="user"]', {
      hasText: "Hello optimistic",
    });
    await expect(userMessage).toBeVisible({ timeout: 500 });

    // The "No messages yet" placeholder should be gone
    await expect(
      page.locator("text=No messages yet. Start the conversation."),
    ).not.toBeVisible();

    // The thinking indicator should be visible below the user message
    const thinkingIndicator = page.locator(
      '[data-testid="thinking-indicator"]',
    );
    await expect(thinkingIndicator).toBeVisible({ timeout: 2_000 });

    await page.screenshot({ path: "/tmp/e2e-106-optimistic-instant.png" });

    // Wait for the assistant response to complete
    await expect(chatInput).toBeEnabled({ timeout: 30_000 });
  });

  test("E2E Test 2: No duplicate message after SSE confirms", async ({
    page,
  }) => {
    await setupSession(page);

    const chatInput = page.locator('textarea[aria-label="Message input"]');
    await expect(chatInput).toBeVisible();

    // Type and send a message
    await chatInput.fill("Check dedup");
    await chatInput.press("Enter");

    // Wait for the assistant response to complete (input re-enabled)
    await expect(chatInput).toBeEnabled({ timeout: 30_000 });

    // Exactly ONE user message with text "Check dedup" should exist
    const userMessages = page.locator('[data-role="user"]', {
      hasText: "Check dedup",
    });
    await expect(userMessages).toHaveCount(1);

    // The assistant response should be visible
    const assistantMessage = page.locator('[data-role="assistant"]');
    await expect(assistantMessage.first()).toBeVisible();

    await page.screenshot({ path: "/tmp/e2e-106-no-duplicate.png" });
  });

  test("E2E Test 3: Follow-up message also renders optimistically", async ({
    page,
  }) => {
    await setupSession(page);

    const chatInput = page.locator('textarea[aria-label="Message input"]');
    await expect(chatInput).toBeVisible();

    // Send first message and wait for assistant to respond
    await chatInput.fill("First message");
    await chatInput.press("Enter");
    await expect(chatInput).toBeEnabled({ timeout: 30_000 });

    // Now send the follow-up
    await chatInput.fill("Follow-up message");
    await chatInput.press("Enter");

    // The follow-up should appear immediately (within 500ms)
    const followUp = page.locator('[data-role="user"]', {
      hasText: "Follow-up message",
    });
    await expect(followUp).toBeVisible({ timeout: 500 });

    // Thinking indicator should be visible
    const thinkingIndicator = page.locator(
      '[data-testid="thinking-indicator"]',
    );
    await expect(thinkingIndicator).toBeVisible({ timeout: 2_000 });

    await page.screenshot({ path: "/tmp/e2e-106-followup-optimistic.png" });

    // Wait for assistant response to complete
    await expect(chatInput).toBeEnabled({ timeout: 30_000 });

    // After completion, exactly ONE "Follow-up message" bubble
    const followUpMessages = page.locator('[data-role="user"]', {
      hasText: "Follow-up message",
    });
    await expect(followUpMessages).toHaveCount(1);
  });
});
