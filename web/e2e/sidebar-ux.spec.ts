import { test, expect } from "@playwright/test";
import { API_BASE } from "./e2e-constants";

/**
 * Helper: create a project via API and return its id.
 */
async function createProject(name: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, path: `/tmp/e2e-${name}` }),
  });
  if (!res.ok) throw new Error(`Failed to create project: ${res.status}`);
  const data = (await res.json()) as { id: string };
  return data.id;
}

// Use unique suffix to avoid collisions with repeated runs
const suffix = Date.now().toString(36);

test.describe("Sidebar UX with many projects", () => {
  const names = {
    alpha: `alpha-web-${suffix}`,
    beta: `beta-api-${suffix}`,
    gamma: `gamma-cli-${suffix}`,
  };
  let projectIds: Record<string, string> = {};

  test.beforeAll(async () => {
    projectIds.alpha = await createProject(names.alpha);
    projectIds.beta = await createProject(names.beta);
    projectIds.gamma = await createProject(names.gamma);
  });

  test("E2E 1: search filters projects", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("sidebar")).toBeVisible();

    // Wait for our projects to load
    await expect(
      page.getByRole("link", { name: names.alpha }),
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("link", { name: names.beta })).toBeVisible();
    await expect(page.getByRole("link", { name: names.gamma })).toBeVisible();

    // Screenshot: all projects visible
    await page.screenshot({ path: "/tmp/sidebar-e2e1-all-projects.png" });

    // Type search query
    const searchInput = page.getByTestId("sidebar-search");
    await searchInput.fill(`alpha-web-${suffix}`);

    // Only alpha should be visible
    await expect(
      page.getByRole("link", { name: names.alpha }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: names.beta }),
    ).not.toBeVisible();
    await expect(
      page.getByRole("link", { name: names.gamma }),
    ).not.toBeVisible();

    // Screenshot: filtered state
    await page.screenshot({ path: "/tmp/sidebar-e2e1-filtered.png" });

    // Clear search
    await searchInput.clear();

    // All our projects visible again
    await expect(
      page.getByRole("link", { name: names.alpha }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: names.beta })).toBeVisible();
    await expect(page.getByRole("link", { name: names.gamma })).toBeVisible();

    // Screenshot: restored state
    await page.screenshot({ path: "/tmp/sidebar-e2e1-restored.png" });
  });

  test("E2E 2: time grouping is displayed", async ({ page }) => {
    await page.goto("/");
    const sidebar = page.getByTestId("sidebar");

    // Wait for our projects to load in the sidebar
    await expect(
      sidebar.getByRole("link", { name: names.alpha }),
    ).toBeVisible({ timeout: 10_000 });

    // At least one time group header should be visible (projects may be in "today" or "yesterday" depending on UTC time)
    const anyGroup = page.locator('[data-testid^="time-group-"]:not([data-testid$="-toggle"])').first();
    await expect(anyGroup).toBeVisible();

    // Screenshot: groups visible
    await page.screenshot({ path: "/tmp/sidebar-e2e2-groups.png" });

    // Click first group's toggle to collapse
    const groupTestId = await anyGroup.getAttribute("data-testid");
    const groupKey = groupTestId!.replace("time-group-", "");
    const toggleBtn = page.getByTestId(`time-group-toggle-${groupKey}`);
    await toggleBtn.click();

    // Projects in that group should be hidden in sidebar
    await expect(
      sidebar.getByRole("link", { name: names.alpha }),
    ).not.toBeVisible();

    // Screenshot: collapsed group
    await page.screenshot({ path: "/tmp/sidebar-e2e2-collapsed.png" });

    // Click again to expand
    await toggleBtn.click();
    await expect(
      sidebar.getByRole("link", { name: names.alpha }),
    ).toBeVisible();
  });

  test("E2E 3: New Project button navigates correctly", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("sidebar")).toBeVisible();

    const newProjectBtn = page.getByTestId("sidebar-new-project");
    await expect(newProjectBtn).toBeVisible();

    // Screenshot: button visible
    await page.screenshot({ path: "/tmp/sidebar-e2e3-button.png" });

    await newProjectBtn.click();

    // URL should be /projects/new
    await expect(page).toHaveURL(/\/projects\/new/);
    await expect(
      page.locator("h1", { hasText: "New Project" }),
    ).toBeVisible();
  });

  test("E2E 4: active project highlighting", async ({ page }) => {
    // Navigate to first project
    await page.goto(`/projects/${projectIds.alpha}`);

    // Wait for sidebar to load
    await expect(
      page.getByRole("link", { name: names.alpha }),
    ).toBeVisible({ timeout: 10_000 });

    // The active project link in the sidebar
    const firstLink = page
      .getByTestId("sidebar")
      .getByRole("link", { name: names.alpha });
    await expect(firstLink).toHaveClass(/font-medium/);
    await expect(firstLink).toHaveClass(/bg-gray-800/);

    // Screenshot: first project active
    await page.screenshot({
      path: "/tmp/sidebar-e2e4-first-active.png",
    });

    // Navigate to second project
    await page.goto(`/projects/${projectIds.beta}`);
    await expect(
      page.getByRole("link", { name: names.beta }),
    ).toBeVisible({ timeout: 10_000 });

    const secondLink = page
      .getByTestId("sidebar")
      .getByRole("link", { name: names.beta });
    await expect(secondLink).toHaveClass(/font-medium/);

    // First project should no longer be highlighted
    const firstLinkAfter = page
      .getByTestId("sidebar")
      .getByRole("link", { name: names.alpha });
    await expect(firstLinkAfter).not.toHaveClass(/font-medium/);

    // Screenshot: second project active
    await page.screenshot({
      path: "/tmp/sidebar-e2e4-second-active.png",
    });
  });

  test("E2E 5: sidebar collapse preserves functionality", async ({
    page,
  }) => {
    await page.goto("/");

    const sidebar = page.getByTestId("sidebar");
    await expect(sidebar).toBeVisible();

    // Sidebar should be expanded: search input visible
    const searchInput = page.getByTestId("sidebar-search");
    await expect(searchInput).toBeVisible({ timeout: 10_000 });

    // Screenshot: expanded
    await page.screenshot({ path: "/tmp/sidebar-e2e5-expanded.png" });

    // Collapse
    const toggle = page.getByTestId("sidebar-toggle");
    await toggle.click();

    // Search input should be hidden
    await expect(searchInput).not.toBeVisible();

    // Sidebar should have narrow width class
    await expect(sidebar).toHaveClass(/w-12/);

    // Screenshot: collapsed
    await page.screenshot({ path: "/tmp/sidebar-e2e5-collapsed.png" });

    // Reload page -- collapsed state should persist
    await page.reload();
    await expect(page.getByTestId("sidebar")).toHaveClass(/w-12/);
    await expect(page.getByTestId("sidebar-search")).not.toBeVisible();

    // Expand again
    await page.getByTestId("sidebar-toggle").click();
    await expect(page.getByTestId("sidebar-search")).toBeVisible();
  });

  test("E2E 6: project count display", async ({ page }) => {
    await page.goto("/");

    // Wait for projects to load
    await expect(
      page.getByRole("link", { name: names.alpha }),
    ).toBeVisible({ timeout: 10_000 });

    const countEl = page.getByTestId("sidebar-project-count");
    await expect(countEl).toBeVisible();

    // Should show total count (at least 3)
    const countText = await countEl.textContent();
    expect(countText).toMatch(/Projects \(\d+\)/);
    const match = countText!.match(/Projects \((\d+)\)/);
    expect(Number(match![1])).toBeGreaterThanOrEqual(3);

    // Screenshot: total count
    await page.screenshot({ path: "/tmp/sidebar-e2e6-total-count.png" });

    // Search to filter to exactly one project
    const searchInput = page.getByTestId("sidebar-search");
    await searchInput.fill(names.alpha);

    // Count should show filtered format
    await expect(countEl).toHaveText(/Projects \(1 of \d+\)/);

    // Screenshot: filtered count
    await page.screenshot({
      path: "/tmp/sidebar-e2e6-filtered-count.png",
    });
  });
});
