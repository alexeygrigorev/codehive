import { test, expect } from "@playwright/test";

test.describe("Chat message flow", () => {
  test.beforeAll(() => {
    const hasApiKey = !!(process.env.CODEHIVE_ANTHROPIC_API_KEY || process.env.ANTHROPIC_API_KEY);
    expect(hasApiKey, "CODEHIVE_ANTHROPIC_API_KEY must be set to run e2e tests").toBe(true);
  });

  test("user sends a message and sees the assistant response", async ({ page }) => {
    // 1. Navigate to dashboard
    await page.goto("/");
    await expect(page.locator("h1", { hasText: "Dashboard" })).toBeVisible();

    // 2. Click "New Project" link in the dashboard header
    await page.click('a:has-text("New Project")');
    await expect(page.locator("h1", { hasText: "New Project" })).toBeVisible();

    // 3. Click the "Empty Project" card to reveal the creation form
    await page.click('button:has-text("Empty Project")');

    // 4. Fill in the directory path (required) and project name (optional, auto-derived)
    await page.fill("#dir-path", "/tmp/e2e-test-project");
    await expect(page.locator("#proj-name")).toHaveValue("e2e-test-project");

    // 5. Click "Create Project" — app auto-redirects to the project page
    await page.click('button:has-text("Create Project")');

    // 6. Wait for the project page to load (breadcrumb or project heading appears)
    await expect(
      page.locator("h1", { hasText: "e2e-test-project" }),
    ).toBeVisible({ timeout: 10_000 });

    // 7. Click "+ New Session" — this instantly creates a session and navigates to the chat
    await page.click('button:has-text("+ New Session")');

    // 8. Wait for chat panel to be visible
    await expect(page.locator(".chat-panel")).toBeVisible({ timeout: 10_000 });

    // 9. Type a message in the chat textarea (identified by aria-label)
    const chatInput = page.locator('textarea[aria-label="Message input"]');
    await expect(chatInput).toBeVisible();
    await chatInput.fill("What is 2 + 2?");
    await chatInput.press("Enter");

    // 10. Verify the user message appears in the chat
    const userMessage = page.locator('[data-role="user"]', { hasText: "What is 2 + 2?" });
    await expect(userMessage).toBeVisible({ timeout: 5_000 });

    // 11. Verify an assistant response appears (wait for LLM streaming to complete)
    const assistantMessage = page.locator('[data-role="assistant"]');
    await expect(assistantMessage.first()).toBeVisible({ timeout: 30_000 });

    // 12. Verify the assistant message has actual content (not empty)
    const content = await assistantMessage.first().textContent();
    expect(content).toBeTruthy();
    expect(content!.length).toBeGreaterThan(0);
  });
});
