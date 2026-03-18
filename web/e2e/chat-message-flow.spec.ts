import { test, expect } from "@playwright/test";

test.describe("Chat message flow", () => {
  test("user sends a message and sees the assistant response", async ({ page }) => {
    // 1. Navigate to dashboard
    await page.goto("/");
    await expect(page.locator("text=Projects")).toBeVisible();

    // 2. Create a project (or use existing)
    //    Click "+ New Project" button, fill in name, submit
    await page.click('button:has-text("New Project"), a:has-text("New Project")');
    const projectNameInput = page.locator('input[name="name"], input[placeholder*="name" i]');
    await projectNameInput.fill("E2E Test Project");
    // Fill required path field if present
    const pathInput = page.locator('input[name="path"], input[placeholder*="path" i]');
    if (await pathInput.isVisible()) {
      await pathInput.fill("/tmp/e2e-test-project");
    }
    await page.click('button[type="submit"], button:has-text("Create")');

    // 3. Navigate to the project and create a session
    await page.click('text=E2E Test Project');
    await page.click('button:has-text("New Session"), a:has-text("New Session")');
    const sessionNameInput = page.locator('input[name="name"], input[placeholder*="name" i]');
    if (await sessionNameInput.isVisible()) {
      await sessionNameInput.fill("E2E Chat Test");
      await page.click('button[type="submit"], button:has-text("Create")');
    }

    // 4. Wait for chat panel to be visible
    await expect(page.locator(".chat-panel")).toBeVisible({ timeout: 10_000 });

    // 5. Type a message in the chat input
    const chatInput = page.locator(
      '.chat-panel textarea, .chat-panel input[type="text"]'
    );
    await chatInput.fill("What is 2 + 2?");
    await chatInput.press("Enter");

    // 6. Verify the user message appears
    await expect(page.locator('text="What is 2 + 2?"')).toBeVisible({ timeout: 5_000 });

    // 7. Verify an assistant response appears (wait for streaming to complete)
    //    The assistant bubble has data-role="assistant" or a distinct CSS class.
    //    We wait for any new message bubble that is NOT the user's message.
    const assistantMessage = page.locator(
      '.chat-panel [data-role="assistant"], .chat-panel .message-assistant'
    );
    await expect(assistantMessage.first()).toBeVisible({ timeout: 30_000 });

    // 8. Verify the assistant message has actual content (not empty)
    const content = await assistantMessage.first().textContent();
    expect(content).toBeTruthy();
    expect(content!.length).toBeGreaterThan(0);
  });
});
