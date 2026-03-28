import { test, expect } from "@playwright/test";
import { API_BASE } from "./e2e-constants";

/**
 * Navigate to the New Project page and expand the Empty Project form.
 */
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

test.describe("Windows Path Support", () => {
  test("Test 1: Windows path accepted, name derived, project created", async ({
    page,
  }) => {
    await openEmptyProjectForm(page);

    const dirInput = page.locator("#dir-path");
    const nameInput = page.locator("#proj-name");

    // Clear pre-filled path and type a Windows path
    await dirInput.clear();
    await dirInput.fill("C:\\Users\\alexey\\git\\myapp");

    // Assert project name auto-derived
    await expect(nameInput).toHaveValue("myapp");

    // Assert no validation error is visible
    await expect(page.locator(".text-red-600")).not.toBeVisible();

    // Take screenshot
    await page.screenshot({
      path: "/tmp/e2e-166-windows-path-form.png",
    });

    // Click Create Project
    await page.locator("button", { hasText: "Create Project" }).click();

    // Assert redirect to /projects/<uuid>
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+/, {
      timeout: 15_000,
    });

    // Assert the page shows the project name
    await expect(page.locator("body")).toContainText("myapp", {
      timeout: 10_000,
    });

    await page.screenshot({
      path: "/tmp/e2e-166-windows-path-created.png",
    });
  });

  test("Test 2: Unix path still works (regression guard)", async ({
    page,
  }) => {
    await openEmptyProjectForm(page);

    const dirInput = page.locator("#dir-path");
    const nameInput = page.locator("#proj-name");

    await dirInput.clear();
    await dirInput.fill("/home/user/projects/myapp");

    // Assert project name auto-derived
    await expect(nameInput).toHaveValue("myapp");

    // Assert no validation error
    await expect(page.locator(".text-red-600")).not.toBeVisible();

    // Click Create Project
    await page.locator("button", { hasText: "Create Project" }).click();

    // Assert redirect
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+/, {
      timeout: 15_000,
    });

    await page.screenshot({
      path: "/tmp/e2e-166-unix-path-created.png",
    });
  });

  test("Test 3: UNC path accepted, name derived", async ({ page }) => {
    await openEmptyProjectForm(page);

    const dirInput = page.locator("#dir-path");
    const nameInput = page.locator("#proj-name");

    await dirInput.clear();
    await dirInput.fill("\\\\fileserver\\shared\\projects\\webapp");

    // Assert project name auto-derived
    await expect(nameInput).toHaveValue("webapp");

    // Assert no validation error
    await expect(page.locator(".text-red-600")).not.toBeVisible();

    await page.screenshot({
      path: "/tmp/e2e-166-unc-path-form.png",
    });

    // Click Create Project -- may fail on backend since path doesn't exist,
    // but the point is the frontend validation does NOT block it
    await page.locator("button", { hasText: "Create Project" }).click();

    // Wait briefly for the request to complete
    // Either we get redirected (success) or we get a backend error displayed
    // but NOT the "Path must be absolute" frontend validation error
    await page.waitForTimeout(2000);

    // The "Path must be absolute" error should NOT appear
    const pathAbsoluteError = page.locator("text=Path must be absolute");
    await expect(pathAbsoluteError).not.toBeVisible();

    await page.screenshot({
      path: "/tmp/e2e-166-unc-path-result.png",
    });
  });

  test("Test 4: Relative path still rejected", async ({ page }) => {
    await openEmptyProjectForm(page);

    const dirInput = page.locator("#dir-path");

    await dirInput.clear();
    await dirInput.fill("relative/path/here");

    // Click Create Project
    await page.locator("button", { hasText: "Create Project" }).click();

    // Assert error text is visible and contains "absolute"
    const errorEl = page.locator(".text-red-600");
    await expect(errorEl).toBeVisible();
    await expect(errorEl).toContainText("absolute");

    // Assert URL has NOT changed
    await expect(page).toHaveURL(/\/projects\/new/);

    await page.screenshot({
      path: "/tmp/e2e-166-relative-path-rejected.png",
    });
  });

  test("Test 5: Clone destination uses correct separator for Windows default dir", async ({
    page,
  }) => {
    // Mock the default-directory API to return a Windows path
    await page.route("**/api/system/default-directory", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          default_directory: "C:\\Users\\alexey\\projects\\",
        }),
      });
    });

    // Mock gh status as available
    await page.route("**/api/github/status", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          available: true,
          authenticated: true,
          username: "testuser",
        }),
      });
    });

    // Mock repos list with one repo
    await page.route("**/api/github/repos**", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          repos: [
            {
              name: "cool-project",
              full_name: "testuser/cool-project",
              clone_url: "https://github.com/testuser/cool-project.git",
              description: "A cool project",
              language: "TypeScript",
              is_private: false,
              updated_at: "2026-03-01T00:00:00Z",
            },
          ],
        }),
      });
    });

    await page.goto("/");
    await page.getByTestId("sidebar-new-project").click();
    await expect(page).toHaveURL(/\/projects\/new/);

    // Click "From Repository" card
    const repoCard = page.getByTestId("flow-card-start_from_repo");
    await repoCard.click();

    // Wait for repo list to load
    const repoRow = page.getByTestId("repo-row-cool-project");
    await expect(repoRow).toBeVisible({ timeout: 10_000 });

    // Select the repo
    await repoRow.click();

    // Assert clone destination uses backslash
    const cloneDestInput = page.getByTestId("clone-dest-input");
    await expect(cloneDestInput).toHaveValue(
      "C:\\Users\\alexey\\projects\\cool-project",
    );

    await page.screenshot({
      path: "/tmp/e2e-166-clone-dest-windows.png",
    });
  });
});
