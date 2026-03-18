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
    const flowTitles = ["Brainstorm", "Guided Interview", "From Notes", "From Repository"];
    for (const title of flowTitles) {
      const h3 = page
        .locator("button")
        .filter({ hasText: title })
        .locator("h3");
      await expect(h3).toBeVisible();
      const classes = await h3.getAttribute("class");
      expect(classes).toContain("dark:text-gray-100");
    }

    // Take screenshot of the page in dark mode
    await page.screenshot({ path: "/tmp/123-new-project-dark.png" });

    // Click "From Notes" to reveal input section
    await page
      .locator("button")
      .filter({ hasText: "From Notes" })
      .click();

    // Verify the label has dark:text-gray-200
    const label = page.locator('label[for="initial-input"]');
    await expect(label).toBeVisible();
    const labelClasses = await label.getAttribute("class");
    expect(labelClasses).toContain("dark:text-gray-200");

    // Take screenshot of expanded state
    await page.screenshot({ path: "/tmp/123-new-project-dark-expanded.png" });
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
      page.locator("button").filter({ hasText: "Brainstorm" }),
    ).toBeVisible();

    // Take screenshot for visual comparison
    await page.screenshot({ path: "/tmp/123-new-project-light.png" });
  });
});
