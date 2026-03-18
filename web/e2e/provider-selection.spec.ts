import { test, expect } from "@playwright/test";

test.describe("Provider selection during session creation", () => {
  test("user creates a session with provider selection dialog", async ({
    page,
  }) => {
    // 1. Navigate to dashboard
    await page.goto("/");
    await expect(page.locator("h1", { hasText: "Dashboard" })).toBeVisible();

    // 2. Create a project first
    await page.click('a:has-text("New Project")');
    await expect(
      page.locator("h1", { hasText: "New Project" }),
    ).toBeVisible();
    await page.click('button:has-text("Empty Project")');
    await page.fill("#dir-path", "/tmp/e2e-provider-test");
    await expect(page.locator("#proj-name")).toHaveValue("e2e-provider-test");
    await page.click('button:has-text("Create Project")');

    // 3. Wait for the project page
    await expect(
      page.locator("h1", { hasText: "e2e-provider-test" }),
    ).toBeVisible({ timeout: 10_000 });

    // 4. Click "+ New Session" - should open dialog
    await page.click('button:has-text("+ New Session")');

    // 5. Verify dialog appears with provider dropdown
    await expect(page.locator('[data-testid="new-session-dialog"]')).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.locator('[data-testid="provider-select"]')).toBeVisible();

    // 6. Verify "anthropic" is selected by default
    const providerSelect = page.locator('[data-testid="provider-select"]');
    await expect(providerSelect).toHaveValue("anthropic");

    // 7. Verify model field shows default Anthropic model
    const modelInput = page.locator('[data-testid="model-input"]');
    await expect(modelInput).toHaveValue("claude-sonnet-4-20250514");

    // 8. Take screenshot of dialog with default provider
    await page.screenshot({ path: "/tmp/provider-dialog-default.png" });

    // 9. Select Z.ai provider
    await providerSelect.selectOption("zai");

    // 10. Verify model field updates to glm-4.7
    await expect(modelInput).toHaveValue("glm-4.7");

    // 11. Take screenshot of dialog with Z.ai selected
    await page.screenshot({ path: "/tmp/provider-dialog-zai.png" });

    // 12. Switch back to Anthropic and create
    await providerSelect.selectOption("anthropic");
    await expect(modelInput).toHaveValue("claude-sonnet-4-20250514");

    // 13. Click Create
    await page.click('[data-testid="create-session-btn"]');

    // 14. Verify redirect to session page
    await expect(page.locator('[data-testid="session-header"]')).toBeVisible({
      timeout: 10_000,
    });

    // 15. Verify provider badge is visible
    await expect(page.locator('[data-testid="provider-badge"]')).toBeVisible();
    await expect(page.locator('[data-testid="provider-badge"]')).toContainText(
      "Anthropic",
    );

    // 16. Take screenshot of session page with provider badge
    await page.screenshot({ path: "/tmp/provider-badge-session.png" });
  });
});
