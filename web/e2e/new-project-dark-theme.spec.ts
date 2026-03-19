import { test, expect } from "@playwright/test";

test.describe("New Project page dark theme contrast", () => {
  test("E2E: dark mode - all titles and labels are readable", async ({
    page,
  }) => {
    // Enable dark mode via color scheme emulation
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/projects/new");

    // Verify "Empty Project" h3 has dark:text-gray-100
    const emptyProjectTitle = page
      .locator("button")
      .filter({ hasText: "Empty Project" })
      .locator("h3");
    await expect(emptyProjectTitle).toBeVisible();
    const emptyClasses = await emptyProjectTitle.getAttribute("class");
    expect(emptyClasses).toContain("dark:text-gray-100");

    // Verify all four flow-type card h3 titles have dark:text-gray-100
    const flowTestIds = [
      "flow-card-brainstorm",
      "flow-card-interview",
      "flow-card-spec_from_notes",
      "flow-card-start_from_repo",
    ];
    for (const testId of flowTestIds) {
      const h3 = page.getByTestId(testId).locator("h3");
      await expect(h3).toBeVisible();
      const classes = await h3.getAttribute("class");
      expect(classes).toContain("dark:text-gray-100");
    }

    // Take screenshot of the page in dark mode
    await page.screenshot({ path: "/tmp/123-new-project-dark.png" });
  });

  test("E2E: light mode - no regression", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/projects/new");

    // Verify page renders with all expected elements
    await expect(
      page.locator("h1").filter({ hasText: "New Project" }),
    ).toBeVisible();
    await expect(
      page.locator("button").filter({ hasText: "Empty Project" }),
    ).toBeVisible();
    await expect(
      page.getByTestId("flow-card-brainstorm"),
    ).toBeVisible();

    // Take screenshot for visual comparison
    await page.screenshot({ path: "/tmp/123-new-project-light.png" });
  });
});
