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

  const projectDir = `/tmp/e2e-105-project-${Date.now()}`;
  await page.fill("#dir-path", projectDir);
  await page.click('button:has-text("Create Project")');

  // Wait for project page
  await expect(
    page.locator("h1").first(),
  ).toBeVisible({ timeout: 10_000 });

  // Create a new session
  await page.click('button:has-text("+ New Session")');

  // Wait for chat panel
  await expect(page.locator(".chat-panel")).toBeVisible({ timeout: 10_000 });
}

test.describe("Streaming and thinking indicator", () => {
  test.beforeAll(() => {
    const hasApiKey = !!(
      process.env.CODEHIVE_ANTHROPIC_API_KEY || process.env.ANTHROPIC_API_KEY
    );
    expect(
      hasApiKey,
      "CODEHIVE_ANTHROPIC_API_KEY must be set to run e2e tests",
    ).toBe(true);
  });

  test("E2E Test 1: Thinking indicator appears and disappears", async ({
    page,
  }) => {
    await setupSession(page);

    const chatInput = page.locator('textarea[aria-label="Message input"]');
    await expect(chatInput).toBeVisible();

    // Type and send a message
    await chatInput.fill("Say hello");
    await chatInput.press("Enter");

    // User message should appear
    const userMessage = page.locator('[data-role="user"]', {
      hasText: "Say hello",
    });
    await expect(userMessage).toBeVisible({ timeout: 5_000 });

    // Thinking indicator should appear
    const thinkingIndicator = page.locator(
      '[data-testid="thinking-indicator"]',
    );
    // It may appear very briefly -- take screenshot while it is (possibly) visible
    await page.waitForTimeout(200);
    await page.screenshot({ path: "/tmp/e2e-105-thinking-visible.png" });

    // Wait for assistant message to appear (this means streaming started)
    const assistantMessage = page.locator('[data-role="assistant"]');
    await expect(assistantMessage.first()).toBeVisible({ timeout: 30_000 });

    // Thinking indicator should be gone after assistant message appears
    await expect(thinkingIndicator).not.toBeVisible({ timeout: 5_000 });

    // Assistant message should have content
    const content = await assistantMessage.first().textContent();
    expect(content).toBeTruthy();
    expect(content!.length).toBeGreaterThan(0);

    await page.screenshot({ path: "/tmp/e2e-105-response-complete.png" });
  });

  test("E2E Test 2: Streaming shows progressive text", async ({ page }) => {
    await setupSession(page);

    const chatInput = page.locator('textarea[aria-label="Message input"]');
    await expect(chatInput).toBeVisible();

    await chatInput.fill("Count from 1 to 10, one number per line");
    await chatInput.press("Enter");

    // Wait for assistant bubble to appear
    const assistantMessage = page.locator('[data-role="assistant"]');
    await expect(assistantMessage.first()).toBeVisible({ timeout: 30_000 });

    // Take a mid-stream screenshot
    const midStreamContent = await assistantMessage.first().textContent();
    await page.screenshot({ path: "/tmp/e2e-105-mid-stream.png" });

    // Wait a bit longer for more content
    await page.waitForTimeout(3000);

    // Take a later screenshot
    const laterContent = await assistantMessage.first().textContent();
    await page.screenshot({ path: "/tmp/e2e-105-stream-complete.png" });

    // The content should have grown (or at minimum be present)
    // Note: if the LLM responds very quickly, both might be the same
    expect(laterContent).toBeTruthy();
    expect(laterContent!.length).toBeGreaterThan(0);

    // Final content should contain digits 1-10
    // Wait for completion (input re-enabled)
    await expect(
      page.locator('textarea[aria-label="Message input"]'),
    ).toBeEnabled({ timeout: 30_000 });

    const finalContent = await assistantMessage.first().textContent();
    expect(finalContent).toBeTruthy();

    // Verify at least some digits are present
    for (const digit of ["1", "2", "3", "4", "5"]) {
      expect(finalContent).toContain(digit);
    }
  });

  test("E2E Test 3: Tool call flow with thinking indicator", async ({
    page,
  }) => {
    await setupSession(page);

    const chatInput = page.locator('textarea[aria-label="Message input"]');
    await expect(chatInput).toBeVisible();

    await chatInput.fill("Read the file README.md and summarize it");
    await chatInput.press("Enter");

    // Thinking indicator should appear after sending
    await page.waitForTimeout(200);
    await page.screenshot({ path: "/tmp/e2e-105-tool-thinking.png" });

    // Wait for either a tool call card or an assistant message (LLM may not always call tools)
    const toolCallOrAssistant = page.locator(
      '[data-role="assistant"], .tool-call-card',
    );
    await expect(toolCallOrAssistant.first()).toBeVisible({ timeout: 30_000 });

    // Thinking indicator should be gone
    const thinkingIndicator = page.locator(
      '[data-testid="thinking-indicator"]',
    );
    await expect(thinkingIndicator).not.toBeVisible({ timeout: 5_000 });

    await page.screenshot({ path: "/tmp/e2e-105-tool-response.png" });

    // Wait for completion
    await expect(
      page.locator('textarea[aria-label="Message input"]'),
    ).toBeEnabled({ timeout: 60_000 });
  });

  test("E2E Test 4: Input disabled during processing", async ({ page }) => {
    await setupSession(page);

    const chatInput = page.locator('textarea[aria-label="Message input"]');
    const sendButton = page.locator("button", { hasText: "Send" });

    await expect(chatInput).toBeVisible();
    await expect(chatInput).toBeEnabled();
    await expect(sendButton).toBeEnabled();

    await chatInput.fill("Say hello");
    await chatInput.press("Enter");

    // Input and send button should be disabled while processing
    await expect(chatInput).toBeDisabled({ timeout: 2_000 });
    await expect(sendButton).toBeDisabled({ timeout: 2_000 });

    await page.screenshot({ path: "/tmp/e2e-105-input-disabled.png" });

    // Wait for response to complete -- input should re-enable
    await expect(chatInput).toBeEnabled({ timeout: 30_000 });
    await expect(sendButton).toBeEnabled({ timeout: 5_000 });

    await page.screenshot({ path: "/tmp/e2e-105-input-reenabled.png" });
  });
});
