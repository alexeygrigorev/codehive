import { test, expect } from "@playwright/test";
import { API_BASE } from "./e2e-constants";

const COMING_SOON_CARDS = [
  { title: "Brainstorm", testId: "flow-card-brainstorm" },
  { title: "Guided Interview", testId: "flow-card-interview" },
  { title: "From Notes", testId: "flow-card-spec_from_notes" },
  { title: "From Repository", testId: "flow-card-start_from_repo" },
];

test.describe("Project archetypes - Coming soon badges", () => {
  test("E2E: Coming soon badges are visible on all four deferred cards", async ({
    page,
  }) => {
    await page.goto("/projects/new");

    // Verify "New Project" heading is visible
    await expect(
      page.locator("h1").filter({ hasText: "New Project" }),
    ).toBeVisible();

    // Verify Empty Project card is visible and interactive (no Coming soon)
    const emptyProjectBtn = page
      .locator("button")
      .filter({ hasText: "Empty Project" });
    await expect(emptyProjectBtn).toBeVisible();

    // Verify all 4 flow cards show "Coming soon" badge
    for (const card of COMING_SOON_CARDS) {
      const cardEl = page.getByTestId(card.testId);
      await expect(cardEl).toBeVisible();

      // Check for Coming soon badge text within the card
      const badge = cardEl.getByText("Coming soon");
      await expect(badge).toBeVisible();

      // Check that the card has disabled styling (opacity-50)
      const classes = await cardEl.getAttribute("class");
      expect(classes).toContain("opacity-50");
      expect(classes).toContain("cursor-not-allowed");

      // Check aria-disabled
      await expect(cardEl).toHaveAttribute("aria-disabled", "true");
    }

    await page.screenshot({ path: "/tmp/124-coming-soon-light.png" });
  });

  test("E2E: Clicking a Coming soon card does nothing", async ({ page }) => {
    await page.goto("/projects/new");

    // Click the Brainstorm card
    const brainstormCard = page.getByTestId("flow-card-brainstorm");
    await brainstormCard.click();

    // Should still be on /projects/new
    expect(page.url()).toContain("/projects/new");

    // No error messages visible
    const errorText = page.locator("text=Failed");
    await expect(errorText).toHaveCount(0);

    // No loading spinner visible
    const loadingText = page.locator("text=Starting flow...");
    await expect(loadingText).toHaveCount(0);

    // No input area expanded (from notes / repo URL)
    const textarea = page.locator("textarea");
    await expect(textarea).toHaveCount(0);

    await page.screenshot({ path: "/tmp/124-click-coming-soon.png" });
  });

  test("E2E: Empty Project card still works", async ({ page }) => {
    await page.goto("/projects/new");

    // Click Empty Project
    const emptyBtn = page
      .locator("button")
      .filter({ hasText: "Empty Project" });
    await emptyBtn.click();

    // Directory path form should appear
    const pathInput = page.locator("#dir-path");
    await expect(pathInput).toBeVisible();

    // Type a path
    await pathInput.fill("/tmp/test-project");

    // Name should auto-fill
    const nameInput = page.locator("#proj-name");
    await expect(nameInput).toHaveValue("test-project");

    // Click Create Project
    const createBtn = page.locator("button").filter({ hasText: "Create Project" });
    await createBtn.click();

    // Should navigate away from /projects/new to the project page
    await page.waitForURL(/\/projects\/[^/]+$/);
    expect(page.url()).toMatch(/\/projects\/[^/]+$/);

    await page.screenshot({ path: "/tmp/124-empty-project-created.png" });
  });

  test("E2E: Dark mode contrast for Coming soon cards", async ({ page }) => {
    // Enable dark mode
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/projects/new");

    // Verify all 4 Coming soon badges are visible
    for (const card of COMING_SOON_CARDS) {
      const cardEl = page.getByTestId(card.testId);
      await expect(cardEl).toBeVisible();

      const badge = cardEl.getByText("Coming soon");
      await expect(badge).toBeVisible();

      // Verify badge has dark mode classes
      const badgeClasses = await badge.getAttribute("class");
      expect(badgeClasses).toContain("dark:bg-gray-700");
      expect(badgeClasses).toContain("dark:text-gray-300");
    }

    // Verify Empty Project title is visible
    const emptyTitle = page
      .locator("button")
      .filter({ hasText: "Empty Project" })
      .locator("h3");
    await expect(emptyTitle).toBeVisible();

    await page.screenshot({ path: "/tmp/124-coming-soon-dark.png" });
  });
});
