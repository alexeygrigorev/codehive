import { test, expect } from "@playwright/test";
import { API_BASE } from "./e2e-constants";
import fs from "fs";
import path from "path";

const suffix = Date.now().toString(36);

async function getDefaultDirectory(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/system/default-directory`);
  if (!res.ok)
    throw new Error(`Failed to fetch default directory: ${res.status}`);
  const data = (await res.json()) as { default_directory: string };
  return data.default_directory;
}

async function openEmptyProjectForm(
  page: import("@playwright/test").Page,
): Promise<void> {
  await page.goto("/");
  await page.getByTestId("sidebar-new-project").click();
  await expect(page).toHaveURL(/\/projects\/new/);
  await page
    .locator("button")
    .filter({ hasText: "Empty Project" })
    .click();
  await expect(page.locator("#dir-path")).toBeVisible();
}

test.describe("Git init checkbox UX (#152)", () => {
  let defaultDir: string;
  const gitDirName = `e2e-git-ux-${suffix}`;
  const plainDirName = `e2e-plain-ux-${suffix}`;
  let gitDirPath: string;
  let plainDirPath: string;

  test.beforeAll(async () => {
    defaultDir = await getDefaultDirectory();
    const baseDir = defaultDir.replace(/\/+$/, "");
    fs.mkdirSync(baseDir, { recursive: true });

    // Create a directory with .git inside
    gitDirPath = path.join(baseDir, gitDirName);
    fs.mkdirSync(path.join(gitDirPath, ".git"), { recursive: true });

    // Create a plain directory without .git
    plainDirPath = path.join(baseDir, plainDirName);
    fs.mkdirSync(plainDirPath, { recursive: true });
  });

  test.afterAll(() => {
    try {
      fs.rmSync(gitDirPath, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
    try {
      fs.rmSync(plainDirPath, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  });

  test("selecting a git directory shows indicator and hides checkbox", async ({
    page,
  }) => {
    await openEmptyProjectForm(page);

    const browsePanel = page.getByTestId("browse-panel");
    await expect(browsePanel).toBeVisible({ timeout: 10_000 });

    const gitEntry = page.getByTestId(`browse-entry-${gitDirName}`);
    await expect(gitEntry).toBeVisible({ timeout: 10_000 });

    await gitEntry.click();

    // Indicator should be visible
    const indicator = page.getByTestId("git-detected-indicator");
    await expect(indicator).toBeVisible();
    await expect(indicator).toContainText("Git repository detected");

    // Checkbox should not be visible
    await expect(page.getByTestId("git-init-checkbox")).not.toBeVisible();

    // Screenshot
    await page.screenshot({ path: "/tmp/152-git-detected-indicator.png" });
  });

  test("selecting a non-git directory shows checkbox and no indicator", async ({
    page,
  }) => {
    await openEmptyProjectForm(page);

    const browsePanel = page.getByTestId("browse-panel");
    await expect(browsePanel).toBeVisible({ timeout: 10_000 });

    const plainEntry = page.getByTestId(`browse-entry-${plainDirName}`);
    await expect(plainEntry).toBeVisible({ timeout: 10_000 });

    await plainEntry.click();

    // Checkbox should be visible and checked
    const checkbox = page.getByTestId("git-init-checkbox");
    await expect(checkbox).toBeVisible();
    await expect(checkbox).toBeChecked();

    // Indicator should not be present
    await expect(
      page.getByTestId("git-detected-indicator"),
    ).not.toBeVisible();

    // Screenshot
    await page.screenshot({ path: "/tmp/152-git-checkbox-normal.png" });
  });
});
