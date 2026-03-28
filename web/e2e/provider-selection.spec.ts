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

    // 6. Verify "claude" is selected by default
    const providerSelect = page.locator('[data-testid="provider-select"]');
    await expect(providerSelect).toHaveValue("claude");

    // 7. Verify model combobox appears with correct default
    const modelCombobox = page.locator('[data-testid="model-combobox"]');
    await expect(modelCombobox).toBeVisible();
    const modelInput = page.locator('[data-testid="model-input"]');
    await expect(modelInput).toHaveValue("claude-sonnet-4-6");

    // 8. Take screenshot of dialog with default provider
    await page.screenshot({ path: "/tmp/provider-dialog-default.png" });

    // 9. Click model input to open dropdown and verify Claude models are listed
    await modelInput.click();
    const modelListbox = page.locator('[data-testid="model-listbox"]');
    await expect(modelListbox).toBeVisible();
    await expect(modelListbox).toContainText("Claude Sonnet 4.6");
    await expect(modelListbox).toContainText("Claude Opus 4.6");
    await expect(modelListbox).toContainText("(claude-sonnet-4-6)");

    // 10. Take screenshot of model dropdown open
    await page.screenshot({ path: "/tmp/provider-dialog-model-dropdown.png" });

    // 11. Select Z.ai provider
    await providerSelect.selectOption("zai");

    // 12. Verify model field updates to claude-sonnet-4-6 (Z.ai default)
    await expect(modelInput).toHaveValue("claude-sonnet-4-6");

    // 13. Take screenshot of dialog with Z.ai selected
    await page.screenshot({ path: "/tmp/provider-dialog-zai.png" });

    // 14. Switch to OpenAI and verify default model changes
    await providerSelect.selectOption("openai");
    await expect(modelInput).toHaveValue("gpt-5.4");

    // 15. Click model input and select a non-default model from dropdown
    await modelInput.click();
    await expect(modelListbox).toBeVisible();
    const o3Option = page.locator('[data-testid="model-listbox"] [role="option"]', {
      hasText: "O3",
    });
    await o3Option.click();
    await expect(modelInput).toHaveValue("o3");

    // 16. Take screenshot of non-default model selected
    await page.screenshot({ path: "/tmp/provider-dialog-openai-o3.png" });

    // 17. Test custom model ID: clear and type a custom value
    await modelInput.clear();
    await modelInput.fill("my-custom-model-preview");
    await expect(modelInput).toHaveValue("my-custom-model-preview");

    // 18. Take screenshot of custom model typed
    await page.screenshot({ path: "/tmp/provider-dialog-custom-model.png" });

    // 19. Switch back to Claude and create
    await providerSelect.selectOption("claude");
    await expect(modelInput).toHaveValue("claude-sonnet-4-6");

    // 20. Click Create
    await page.click('[data-testid="create-session-btn"]');

    // 21. Verify redirect to session page
    await expect(page.locator('[data-testid="session-header"]')).toBeVisible({
      timeout: 10_000,
    });

    // 22. Verify provider badge is visible
    await expect(page.locator('[data-testid="provider-badge"]')).toBeVisible();
    await expect(page.locator('[data-testid="provider-badge"]')).toContainText(
      "Claude",
    );

    // 23. Take screenshot of session page with provider badge
    await page.screenshot({ path: "/tmp/provider-badge-session.png" });
  });
});
