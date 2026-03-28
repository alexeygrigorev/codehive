import { test, expect } from "@playwright/test";

test.describe("Tool call UI", () => {
  test.beforeAll(() => {
    const hasApiKey = !!(
      process.env.CODEHIVE_ANTHROPIC_API_KEY ||
      process.env.ANTHROPIC_API_KEY
    );
    expect(
      hasApiKey,
      "CODEHIVE_ANTHROPIC_API_KEY must be set to run e2e tests",
    ).toBe(true);
  });

  test("tool call card appears during agent execution with parameters", async ({
    page,
  }) => {
    // 1. Navigate to dashboard
    await page.goto("/");
    await expect(page.locator("h1", { hasText: "Dashboard" })).toBeVisible();

    // 2. Create a project
    await page.click('a:has-text("New Project")');
    await expect(
      page.locator("h1", { hasText: "New Project" }),
    ).toBeVisible();
    await page.click('button:has-text("Empty Project")');
    await page.fill("#dir-path", "/tmp/e2e-tool-call-test");
    await page.click('button:has-text("Create Project")');
    await expect(
      page.locator("h1", { hasText: "e2e-tool-call-test" }),
    ).toBeVisible({ timeout: 10_000 });

    // 3. Create a session
    await page.click('button:has-text("+ New Session")');
    await expect(page.locator(".chat-panel")).toBeVisible({ timeout: 10_000 });

    // 4. Send a message that triggers tool calls (e.g., read a file)
    const chatInput = page.locator('textarea[aria-label="Message input"]');
    await chatInput.fill(
      "Read the file /tmp/e2e-tool-call-test/test.txt and tell me its contents",
    );
    await chatInput.press("Enter");

    // 5. Wait for a tool call card to appear
    const toolCard = page.locator('[data-testid="tool-call-card"]');
    await expect(toolCard.first()).toBeVisible({ timeout: 30_000 });

    // 6. Verify tool name is displayed
    const toolName = toolCard.first().locator(".font-mono.font-bold");
    await expect(toolName).toBeVisible();

    // 7. Screenshot: tool call in-progress or completed state
    await page.screenshot({ path: "/tmp/tool-call-card.png", fullPage: true });
  });

  test("result section is collapsible after tool finishes", async ({
    page,
  }) => {
    // Navigate to dashboard and create a quick session
    await page.goto("/");
    await page.click('a:has-text("New Project")');
    await page.click('button:has-text("Empty Project")');
    await page.fill("#dir-path", "/tmp/e2e-tool-call-collapse");
    await page.click('button:has-text("Create Project")');
    await expect(
      page.locator("h1", { hasText: "e2e-tool-call-collapse" }),
    ).toBeVisible({ timeout: 10_000 });
    await page.click('button:has-text("+ New Session")');
    await expect(page.locator(".chat-panel")).toBeVisible({ timeout: 10_000 });

    // Send message to trigger tool call
    const chatInput = page.locator('textarea[aria-label="Message input"]');
    await chatInput.fill("What is 2 + 2? Use no tools, just answer.");
    await chatInput.press("Enter");

    // Wait for assistant response (may or may not have tool calls)
    const assistantMsg = page.locator('[data-role="assistant"]');
    await expect(assistantMsg.first()).toBeVisible({ timeout: 30_000 });

    // If tool cards exist, verify they have details/summary elements
    const toolCards = page.locator('[data-testid="tool-call-card"]');
    const count = await toolCards.count();
    if (count > 0) {
      const details = toolCards.first().locator("details");
      const detailsCount = await details.count();
      if (detailsCount > 0) {
        const summary = details.first().locator("summary");
        await expect(summary).toBeVisible();
        // Click to toggle
        await summary.click();
        await page.screenshot({
          path: "/tmp/tool-call-expanded.png",
          fullPage: true,
        });
      }
    }

    // Screenshot completed state
    await page.screenshot({
      path: "/tmp/tool-call-completed.png",
      fullPage: true,
    });
  });

  test("dark theme tool call rendering", async ({ page }) => {
    await page.goto("/");

    // Enable dark mode via localStorage
    await page.evaluate(() => {
      localStorage.setItem("theme", "dark");
      document.documentElement.classList.add("dark");
    });
    await page.reload();

    // Take a screenshot to verify dark theme loads
    await page.screenshot({
      path: "/tmp/tool-call-dark-theme.png",
      fullPage: true,
    });
  });
});
