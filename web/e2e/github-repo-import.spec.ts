import { test, expect } from "@playwright/test";
import { API_BASE } from "./e2e-constants";
import fs from "fs";
import os from "os";
import path from "path";

const suffix = Date.now().toString(36);
const homeDir = os.homedir();

/**
 * Navigate to the New Project page.
 */
async function goToNewProject(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByTestId("sidebar-new-project").click();
  await expect(page).toHaveURL(/\/projects\/new/);
}

test.describe("GitHub Repo Import E2E", () => {
  test("E2E 1: From Repository card is enabled, opens picker, shows repos", async ({
    page,
  }) => {
    await goToNewProject(page);

    // The "From Repository" card should NOT have a "Coming soon" badge
    const repoCard = page.getByTestId("flow-card-start_from_repo");
    await expect(repoCard).toBeVisible();
    // Should not be aria-disabled
    await expect(repoCard).not.toHaveAttribute("aria-disabled", "true");
    // Should not contain "Coming soon" text
    await expect(repoCard.locator("text=Coming soon")).not.toBeVisible();

    // Click the card
    await repoCard.click();

    // Repo picker panel should appear
    const pickerPanel = page.getByTestId("repo-picker-panel");
    await expect(pickerPanel).toBeVisible();

    // Should show "Checking GitHub access..." briefly
    // Then repos should load (this depends on gh being installed)
    // Wait for either repos list or error
    const repoList = page.getByTestId("repo-list");
    const pickerError = page.getByTestId("repo-picker-error");

    await expect(repoList.or(pickerError)).toBeVisible({ timeout: 15_000 });

    // Take screenshot
    await page.screenshot({
      path: "/tmp/e2e-126-repo-picker-opened.png",
    });

    if (await repoList.isVisible()) {
      // If repos loaded, verify at least one row
      const rows = page.locator('[data-testid^="repo-row-"]');
      const count = await rows.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test("E2E 2: Repo list search and metadata", async ({ page }) => {
    await goToNewProject(page);
    await page.getByTestId("flow-card-start_from_repo").click();

    const repoList = page.getByTestId("repo-list");
    const pickerError = page.getByTestId("repo-picker-error");

    await expect(repoList.or(pickerError)).toBeVisible({ timeout: 15_000 });

    // Skip if gh is not available
    if (await pickerError.isVisible()) {
      test.skip();
      return;
    }

    // Check metadata - at least one repo shows language or visibility badge
    const langBadges = page.locator('[data-testid^="repo-lang-"]');
    const visibilityBadges = page.locator('[data-testid^="repo-visibility-"]');
    const langCount = await langBadges.count();
    const visCount = await visibilityBadges.count();
    expect(langCount + visCount).toBeGreaterThan(0);

    // Test search filtering
    const searchInput = page.getByTestId("repo-search-input");
    const initialRows = page.locator('[data-testid^="repo-row-"]');
    const initialCount = await initialRows.count();

    // Type a search term - use first char of first repo's name to ensure at least one match
    const firstRowTestId = await initialRows
      .first()
      .getAttribute("data-testid");
    const firstRepoName = firstRowTestId?.replace("repo-row-", "") ?? "a";

    await searchInput.fill(firstRepoName.substring(0, 3));

    // Wait for filtering
    await page.waitForTimeout(300);
    const filteredRows = page.locator('[data-testid^="repo-row-"]');
    const filteredCount = await filteredRows.count();

    // Filtered should have fewer or equal results
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
    expect(filteredCount).toBeGreaterThan(0);

    // Clear search - full list should reappear
    await searchInput.fill("");
    await page.waitForTimeout(300);
    const restoredCount = await page
      .locator('[data-testid^="repo-row-"]')
      .count();
    expect(restoredCount).toBe(initialCount);

    await page.screenshot({
      path: "/tmp/e2e-126-repo-search.png",
    });
  });

  test("E2E 3: Select repo and verify clone form", async ({ page }) => {
    await goToNewProject(page);
    await page.getByTestId("flow-card-start_from_repo").click();

    const repoList = page.getByTestId("repo-list");
    const pickerError = page.getByTestId("repo-picker-error");

    await expect(repoList.or(pickerError)).toBeVisible({ timeout: 15_000 });

    if (await pickerError.isVisible()) {
      test.skip();
      return;
    }

    // Click on the first repo
    const firstRow = page.locator('[data-testid^="repo-row-"]').first();
    await firstRow.click();

    // Clone form should appear
    const cloneForm = page.getByTestId("clone-form");
    await expect(cloneForm).toBeVisible();

    // Clone destination should contain the repo name
    const cloneDest = page.getByTestId("clone-dest-input");
    await expect(cloneDest).toBeVisible();
    const destValue = await cloneDest.inputValue();
    expect(destValue.length).toBeGreaterThan(0);

    // Project name field should have the repo name
    const cloneName = page.getByTestId("clone-name-input");
    await expect(cloneName).toBeVisible();
    const nameValue = await cloneName.inputValue();
    expect(nameValue.length).toBeGreaterThan(0);

    // Clone button should be visible
    const cloneButton = page.getByTestId("clone-button");
    await expect(cloneButton).toBeVisible();
    await expect(cloneButton).toHaveText("Clone & Create Project");

    await page.screenshot({
      path: "/tmp/e2e-126-repo-selected.png",
    });
  });

  test("E2E 4: Full clone and project creation", async ({ page }) => {
    await goToNewProject(page);
    await page.getByTestId("flow-card-start_from_repo").click();

    const repoList = page.getByTestId("repo-list");
    const pickerError = page.getByTestId("repo-picker-error");

    await expect(repoList.or(pickerError)).toBeVisible({ timeout: 15_000 });

    if (await pickerError.isVisible()) {
      test.skip();
      return;
    }

    // Search for a small known repo (use "codehive" which should exist)
    const searchInput = page.getByTestId("repo-search-input");
    await searchInput.fill("codehive");
    await page.waitForTimeout(300);

    // Select the first matching repo (or just the first repo if none match)
    let rows = page.locator('[data-testid^="repo-row-"]');
    if ((await rows.count()) === 0) {
      await searchInput.fill("");
      await page.waitForTimeout(300);
      rows = page.locator('[data-testid^="repo-row-"]');
    }

    await rows.first().click();

    // Edit the clone destination to a unique dir under home
    const cloneDest = page.getByTestId("clone-dest-input");
    const uniqueDir = path.join(homeDir, `.codehive-e2e-clone-${suffix}`);
    await cloneDest.fill(uniqueDir);

    // Click clone button
    const cloneButton = page.getByTestId("clone-button");
    await cloneButton.click();

    // Should show cloning indicator
    await expect(cloneButton).toHaveText("Cloning repository...");

    await page.screenshot({
      path: "/tmp/e2e-126-cloning.png",
    });

    // Wait for redirect (clone can take a while)
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+/, {
      timeout: 120_000,
    });

    await page.screenshot({
      path: "/tmp/e2e-126-project-created.png",
    });

    // Clean up cloned directory
    try {
      fs.rmSync(uniqueDir, { recursive: true, force: true });
    } catch {
      // ignore cleanup errors
    }
  });

  test("E2E 5: Clone to existing directory shows error", async ({ page }) => {
    const conflictDir = path.join(homeDir, `.codehive-e2e-conflict-${suffix}`);
    fs.mkdirSync(conflictDir, { recursive: true });

    try {
      await goToNewProject(page);
      await page.getByTestId("flow-card-start_from_repo").click();

      const repoList = page.getByTestId("repo-list");
      const pickerError = page.getByTestId("repo-picker-error");

      await expect(repoList.or(pickerError)).toBeVisible({ timeout: 15_000 });

      if (await pickerError.isVisible()) {
        test.skip();
        return;
      }

      // Select first repo
      const firstRow = page.locator('[data-testid^="repo-row-"]').first();
      await firstRow.click();

      // Set clone destination to the existing directory
      const cloneDest = page.getByTestId("clone-dest-input");
      await cloneDest.fill(conflictDir);

      // Click clone
      await page.getByTestId("clone-button").click();

      // Should show error about existing directory
      const cloneError = page.getByTestId("clone-error");
      await expect(cloneError).toBeVisible({ timeout: 10_000 });
      await expect(cloneError).toContainText("already exists");

      // Should NOT redirect
      await expect(page).toHaveURL(/\/projects\/new/);

      await page.screenshot({
        path: "/tmp/e2e-126-conflict-error.png",
      });
    } finally {
      try {
        fs.rmSync(conflictDir, { recursive: true, force: true });
      } catch {
        // ignore
      }
    }
  });
});
