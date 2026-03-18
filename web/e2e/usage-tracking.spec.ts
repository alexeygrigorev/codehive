import { test, expect } from "@playwright/test";

test.describe("Usage tracking", () => {
  test("E2E 1: Usage page loads and shows structure", async ({ page }) => {
    // Navigate to /usage
    await page.goto("/usage");

    // Page title "Usage" is visible
    await expect(page.locator("h1", { hasText: "Usage" })).toBeVisible();

    // Three summary cards visible
    const summaryCards = page.locator('[data-testid="summary-cards"]');
    await expect(summaryCards).toBeVisible();
    await expect(page.getByTestId("total-requests")).toBeVisible();
    await expect(page.getByTestId("total-tokens")).toBeVisible();
    await expect(page.getByTestId("estimated-cost")).toBeVisible();

    // Usage table visible with correct columns
    const table = page.getByTestId("usage-table");
    await expect(table).toBeVisible();
    await expect(table.locator("th", { hasText: "Date" })).toBeVisible();
    await expect(table.locator("th", { hasText: "Session" })).toBeVisible();
    await expect(table.locator("th", { hasText: "Model" })).toBeVisible();
    await expect(table.locator("th", { hasText: "Input Tokens" })).toBeVisible();
    await expect(table.locator("th", { hasText: "Output Tokens" })).toBeVisible();
    await expect(table.locator("th", { hasText: "Est. Cost" })).toBeVisible();

    // Take screenshot
    await page.screenshot({ path: "/tmp/e2e-usage-page.png", fullPage: true });
  });

  test("E2E 2: Usage page time range filter", async ({ page }) => {
    await page.goto("/usage");
    await expect(page.locator("h1", { hasText: "Usage" })).toBeVisible();

    // Time range selector is visible
    const timeSelect = page.getByTestId("time-range-select");
    await expect(timeSelect).toBeVisible();

    // Default is "This Month"
    await expect(timeSelect).toHaveValue("this_month");

    // Change to "Today"
    await timeSelect.selectOption("today");
    await expect(timeSelect).toHaveValue("today");

    // Summary cards should still be visible (with potentially different data)
    await expect(page.getByTestId("total-requests")).toBeVisible();

    // Change to "All Time"
    await timeSelect.selectOption("all_time");
    await expect(timeSelect).toHaveValue("all_time");
    await expect(page.getByTestId("total-requests")).toBeVisible();

    await page.screenshot({ path: "/tmp/e2e-usage-filter.png", fullPage: true });
  });

  test("E2E 4: Usage page accessible from sidebar nav", async ({ page }) => {
    // Navigate to dashboard
    await page.goto("/");
    await expect(page.locator("h1", { hasText: "Dashboard" })).toBeVisible();

    // Click "Usage" link in sidebar
    const sidebar = page.getByTestId("sidebar");
    await expect(sidebar).toBeVisible();
    const usageLink = sidebar.locator('a[href="/usage"]');
    await expect(usageLink).toBeVisible();
    await usageLink.click();

    // URL should be /usage
    await expect(page).toHaveURL(/\/usage/);

    // Usage page content visible
    await expect(page.locator("h1", { hasText: "Usage" })).toBeVisible();

    await page.screenshot({ path: "/tmp/e2e-usage-sidebar-nav.png", fullPage: true });
  });

  test("E2E 3: Session usage sidebar tab", async ({ page }) => {
    // First create a project and session to navigate to
    await page.goto("/");

    // Try to find an existing session or create one
    // Navigate to /usage first to seed some data context, then create a project+session
    await page.goto("/projects/new");
    await expect(page.locator("h1", { hasText: "New Project" })).toBeVisible();

    // Create an empty project
    await page.click('button:has-text("Empty Project")');
    await page.fill("#dir-path", "/tmp/e2e-usage-test-project");
    await expect(page.locator("#proj-name")).toHaveValue("e2e-usage-test-project");
    await page.click('button:has-text("Create Project")');

    // Wait for the project page
    await expect(
      page.locator("h1", { hasText: "e2e-usage-test-project" }),
    ).toBeVisible({ timeout: 10_000 });

    // Create a session -- opens a modal, fill and submit
    await page.click('button:has-text("+ New Session")');
    await expect(page.locator("text=New Session").first()).toBeVisible({ timeout: 5_000 });
    await page.click('button:has-text("Create")');

    // Wait for the chat panel to load (means we're on the session page)
    await expect(page.locator(".chat-panel")).toBeVisible({ timeout: 10_000 });

    // Wait for session sidebar to be visible
    const sidebar = page.getByTestId("session-sidebar");
    await expect(sidebar).toBeVisible({ timeout: 10_000 });

    // Click the "Usage" tab
    const usageTab = sidebar.locator('button[role="tab"]', { hasText: "Usage" });
    await expect(usageTab).toBeVisible();
    await usageTab.click();

    // The usage panel should appear
    // It may show "No usage data" or "Loading usage..." initially, which is fine
    // because no messages have been sent yet
    const usagePanel = page.getByTestId("usage-panel").or(
      page.locator("text=No usage data available."),
    ).or(
      page.locator("text=Loading usage..."),
    );
    await expect(usagePanel.first()).toBeVisible({ timeout: 5_000 });

    await page.screenshot({ path: "/tmp/e2e-usage-session-sidebar.png", fullPage: true });
  });
});
