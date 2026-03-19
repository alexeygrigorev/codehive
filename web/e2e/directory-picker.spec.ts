import { test, expect } from "@playwright/test";
import { API_BASE } from "./e2e-constants";
import fs from "fs";
import path from "path";

const suffix = Date.now().toString(36);

/**
 * Fetch the configured default directory from the backend.
 */
async function getDefaultDirectory(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/system/default-directory`);
  if (!res.ok)
    throw new Error(`Failed to fetch default directory: ${res.status}`);
  const data = (await res.json()) as { default_directory: string };
  return data.default_directory;
}

/**
 * Navigate to the New Project page and expand the Empty Project form.
 * Returns after the directory path field is visible with a pre-filled value.
 */
async function openEmptyProjectForm(
  page: import("@playwright/test").Page,
): Promise<void> {
  await page.goto("/");
  // Click "New Project" in sidebar
  await page.getByTestId("sidebar-new-project").click();
  await expect(page).toHaveURL(/\/projects\/new/);
  // Click "Empty Project" to expand the form
  await page
    .locator("button")
    .filter({ hasText: "Empty Project" })
    .click();
  // Wait for the directory path input to appear
  await expect(page.locator("#dir-path")).toBeVisible();
}

test.describe("Directory Picker E2E", () => {
  let defaultDir: string;
  const browseDirName = `e2e-browse-test-${suffix}`;
  let browseDirPath: string;

  test.beforeAll(async () => {
    defaultDir = await getDefaultDirectory();
    // Ensure the default directory exists
    fs.mkdirSync(defaultDir.replace(/\/+$/, ""), { recursive: true });

    // Create a test directory with .git inside it for E2E 2
    browseDirPath = path.join(defaultDir.replace(/\/+$/, ""), browseDirName);
    fs.mkdirSync(path.join(browseDirPath, ".git"), { recursive: true });
  });

  test.afterAll(() => {
    // Clean up the test directory
    try {
      fs.rmSync(browseDirPath, { recursive: true, force: true });
    } catch {
      // Ignore cleanup errors
    }
  });

  test("E2E 1: Default directory pre-fill and project creation", async ({
    page,
  }) => {
    await openEmptyProjectForm(page);

    // Wait for the default directory to be fetched and pre-filled
    const dirInput = page.locator("#dir-path");
    await expect(dirInput).toHaveValue(/.+\/$/, { timeout: 10_000 });

    // Verify the pre-filled value matches the backend default
    const prefilled = await dirInput.inputValue();
    expect(prefilled).toBe(defaultDir);

    // Type a project name at the end
    const projectName = `e2e-testproject-${suffix}`;
    await dirInput.click();
    await page.keyboard.press("End");
    await page.keyboard.type(projectName);

    // Assert the project name field auto-derived the name
    const nameInput = page.locator("#proj-name");
    await expect(nameInput).toHaveValue(projectName);

    // Assert git init checkbox is checked by default
    const gitCheckbox = page.getByTestId("git-init-checkbox");
    await expect(gitCheckbox).toBeChecked();

    // Click Create Project
    await page.locator("button", { hasText: "Create Project" }).click();

    // Assert redirect to /projects/<uuid>
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+/, {
      timeout: 15_000,
    });

    // Assert the page shows the project name
    await expect(page.locator("body")).toContainText(projectName, {
      timeout: 10_000,
    });
  });

  test("E2E 2: Directory browser shows subdirectories with git badge", async ({
    page,
  }) => {
    await openEmptyProjectForm(page);

    // Wait for browse panel to appear and load
    const browsePanel = page.getByTestId("browse-panel");
    await expect(browsePanel).toBeVisible({ timeout: 10_000 });

    // Wait for loading to finish (entries should appear)
    const browseEntry = page.getByTestId(`browse-entry-${browseDirName}`);
    await expect(browseEntry).toBeVisible({ timeout: 10_000 });

    // Assert the git badge is visible on the entry
    const gitBadge = browseEntry.locator("text=git");
    await expect(gitBadge).toBeVisible();

    // Click on the entry
    await browseEntry.click();

    // Assert the path field now contains the browse dir path
    const dirInput = page.locator("#dir-path");
    await expect(dirInput).toHaveValue(new RegExp(browseDirName));

    // Assert the git init checkbox is unchecked (already a git repo)
    const gitCheckbox = page.getByTestId("git-init-checkbox");
    await expect(gitCheckbox).not.toBeChecked();

    // Assert "(already a git repo)" text is visible
    await expect(page.locator("text=(already a git repo)")).toBeVisible();
  });

  test("E2E 3: Navigate to parent directory", async ({ page }) => {
    await openEmptyProjectForm(page);

    // Wait for browse panel
    const browsePanel = page.getByTestId("browse-panel");
    await expect(browsePanel).toBeVisible({ timeout: 10_000 });

    // Get current path value
    const dirInput = page.locator("#dir-path");
    await expect(dirInput).toHaveValue(/.+\/$/, { timeout: 10_000 });
    const originalPath = await dirInput.inputValue();

    // Wait for the ".." parent entry to appear (indicating directories loaded)
    const parentButton = page.getByTestId("browse-parent");
    await expect(parentButton).toBeVisible({ timeout: 10_000 });

    // Click ".." to navigate to parent
    await parentButton.click();

    // Assert the path field changed to the parent directory
    await expect(dirInput).not.toHaveValue(originalPath, { timeout: 5_000 });
    const newPath = await dirInput.inputValue();

    // The new path should be the parent of the default directory
    const expectedParent = path.dirname(originalPath.replace(/\/+$/, ""));
    expect(newPath).toBe(expectedParent);

    // Assert the browse panel shows a different list (wait for it to refresh)
    // The old browse entry for our test dir should not be at this level
    // (it was inside the default dir, not its parent)
    await expect(browsePanel).toBeVisible();
  });

  test("E2E 4: Create project without git init", async ({ page }) => {
    await openEmptyProjectForm(page);

    // Wait for default directory to load
    const dirInput = page.locator("#dir-path");
    await expect(dirInput).toHaveValue(/.+\/$/, { timeout: 10_000 });

    // Type a unique project path
    const projectName = `e2e-nogit-${suffix}`;
    await dirInput.click();
    await page.keyboard.press("End");
    await page.keyboard.type(projectName);

    // Uncheck git init checkbox
    const gitCheckbox = page.getByTestId("git-init-checkbox");
    await expect(gitCheckbox).toBeChecked();
    await gitCheckbox.uncheck();
    await expect(gitCheckbox).not.toBeChecked();

    // Click Create Project
    await page.locator("button", { hasText: "Create Project" }).click();

    // Assert redirect to project page
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+/, {
      timeout: 15_000,
    });

    // Verify no .git directory was created
    const createdDir = path.join(
      defaultDir.replace(/\/+$/, ""),
      projectName,
    );
    // Wait a moment for filesystem operations to complete
    const hasGit = fs.existsSync(path.join(createdDir, ".git"));
    expect(hasGit).toBe(false);
  });
});
