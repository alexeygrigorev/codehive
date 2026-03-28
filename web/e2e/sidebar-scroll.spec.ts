import { test, expect } from "@playwright/test";
import { API_BASE } from "./e2e-constants";

/**
 * Helper: create a project via API and return its id.
 */
async function createProject(name: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, path: `/tmp/e2e-scroll-${name}` }),
  });
  if (!res.ok) throw new Error(`Failed to create project: ${res.status}`);
  const data = (await res.json()) as { id: string };
  return data.id;
}

const suffix = Date.now().toString(36);

test.describe("Sidebar independent scroll", () => {
  test.beforeAll(async () => {
    // Create 25 projects so the sidebar project list overflows
    const promises = Array.from({ length: 25 }, (_, i) =>
      createProject(`scroll-proj-${i.toString().padStart(2, "0")}-${suffix}`),
    );
    await Promise.all(promises);
  });

  test("E2E 1: no page-level scrollbar with many projects", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByTestId("sidebar")).toBeVisible();

    // Wait for projects to appear
    await expect(
      page.getByTestId("sidebar").getByRole("link", {
        name: new RegExp(`scroll-proj-00-${suffix}`),
      }),
    ).toBeVisible({ timeout: 15_000 });

    // Check no page-level scrollbar
    const hasPageScroll = await page.evaluate(
      () =>
        document.documentElement.scrollHeight >
        document.documentElement.clientHeight,
    );
    expect(hasPageScroll).toBe(false);

    await page.screenshot({
      path: "/tmp/sidebar-scroll-e2e1-no-page-scroll.png",
    });
  });

  test("E2E 2: sidebar scrolls independently from main content", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByTestId("sidebar")).toBeVisible();

    // Wait for projects to load
    await expect(
      page.getByTestId("sidebar").getByRole("link", {
        name: new RegExp(`scroll-proj-00-${suffix}`),
      }),
    ).toBeVisible({ timeout: 15_000 });

    // Find the scrollable sidebar container (div.overflow-y-auto inside sidebar)
    const sidebarScrollContainer = page.locator(
      '[data-testid="sidebar"] .overflow-y-auto',
    );
    await expect(sidebarScrollContainer).toBeVisible();

    // Record main content scroll position
    const mainScrollBefore = await page.evaluate(() => {
      const main = document.querySelector("main");
      return main ? main.scrollTop : 0;
    });
    expect(mainScrollBefore).toBe(0);

    // Scroll sidebar container down by 300px
    await sidebarScrollContainer.evaluate((el) => {
      el.scrollTop = 300;
    });

    // Verify sidebar scrolled
    const sidebarScrollTop = await sidebarScrollContainer.evaluate(
      (el) => el.scrollTop,
    );
    expect(sidebarScrollTop).toBeGreaterThan(0);

    // Verify main content did not scroll
    const mainScrollAfter = await page.evaluate(() => {
      const main = document.querySelector("main");
      return main ? main.scrollTop : 0;
    });
    expect(mainScrollAfter).toBe(0);

    await page.screenshot({
      path: "/tmp/sidebar-scroll-e2e2-independent.png",
    });
  });

  test("E2E 3: main content scrolls independently from sidebar", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByTestId("sidebar")).toBeVisible();

    // Wait for projects to load
    await expect(
      page.getByTestId("sidebar").getByRole("link", {
        name: new RegExp(`scroll-proj-00-${suffix}`),
      }),
    ).toBeVisible({ timeout: 15_000 });

    const sidebarScrollContainer = page.locator(
      '[data-testid="sidebar"] .overflow-y-auto',
    );

    // Record sidebar scroll position
    const sidebarScrollBefore = await sidebarScrollContainer.evaluate(
      (el) => el.scrollTop,
    );
    expect(sidebarScrollBefore).toBe(0);

    // Scroll main content down (inject tall content to ensure it overflows)
    await page.evaluate(() => {
      const main = document.querySelector("main");
      if (main) {
        const spacer = document.createElement("div");
        spacer.style.height = "3000px";
        spacer.id = "e2e-spacer";
        main.appendChild(spacer);
        main.scrollTop = 200;
      }
    });

    // Verify sidebar scroll position unchanged
    const sidebarScrollAfter = await sidebarScrollContainer.evaluate(
      (el) => el.scrollTop,
    );
    expect(sidebarScrollAfter).toBe(0);

    await page.screenshot({
      path: "/tmp/sidebar-scroll-e2e3-main-independent.png",
    });
  });

  test("E2E 4: independent scroll works after sidebar collapse/expand", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByTestId("sidebar")).toBeVisible();

    // Wait for projects to load
    await expect(
      page.getByTestId("sidebar").getByRole("link", {
        name: new RegExp(`scroll-proj-00-${suffix}`),
      }),
    ).toBeVisible({ timeout: 15_000 });

    // Verify no page-level scrollbar in expanded state
    let hasPageScroll = await page.evaluate(
      () =>
        document.documentElement.scrollHeight >
        document.documentElement.clientHeight,
    );
    expect(hasPageScroll).toBe(false);

    // Collapse sidebar
    await page.getByTestId("sidebar-toggle").click();
    await expect(page.getByTestId("sidebar")).toHaveClass(/w-12/);

    // Verify no page-level scrollbar in collapsed state
    hasPageScroll = await page.evaluate(
      () =>
        document.documentElement.scrollHeight >
        document.documentElement.clientHeight,
    );
    expect(hasPageScroll).toBe(false);

    // Expand sidebar again
    await page.getByTestId("sidebar-toggle").click();
    await expect(page.getByTestId("sidebar")).toHaveClass(/w-64/);

    // Wait for projects to reappear
    await expect(
      page.getByTestId("sidebar").getByRole("link", {
        name: new RegExp(`scroll-proj-00-${suffix}`),
      }),
    ).toBeVisible({ timeout: 10_000 });

    // Scroll sidebar down
    const sidebarScrollContainer = page.locator(
      '[data-testid="sidebar"] .overflow-y-auto',
    );
    await sidebarScrollContainer.evaluate((el) => {
      el.scrollTop = 300;
    });

    const sidebarScrollTop = await sidebarScrollContainer.evaluate(
      (el) => el.scrollTop,
    );
    expect(sidebarScrollTop).toBeGreaterThan(0);

    // Verify main content scroll is still 0
    const mainScroll = await page.evaluate(() => {
      const main = document.querySelector("main");
      return main ? main.scrollTop : 0;
    });
    expect(mainScroll).toBe(0);

    await page.screenshot({
      path: "/tmp/sidebar-scroll-e2e4-after-toggle.png",
    });
  });

  test("E2E 5: layout works on session page", async ({ page }) => {
    // Create a project and session for this test
    const projectId = await createProject(`scroll-session-${suffix}`);
    const sessionRes = await fetch(
      `${API_BASE}/api/projects/${projectId}/sessions`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      },
    );
    if (!sessionRes.ok)
      throw new Error(`Failed to create session: ${sessionRes.status}`);
    const sessionData = (await sessionRes.json()) as { id: string };

    await page.goto(`/sessions/${sessionData.id}`);
    await expect(page.getByTestId("sidebar")).toBeVisible();

    // Check no page-level scrollbar
    const hasPageScroll = await page.evaluate(
      () =>
        document.documentElement.scrollHeight >
        document.documentElement.clientHeight,
    );
    expect(hasPageScroll).toBe(false);

    await page.screenshot({
      path: "/tmp/sidebar-scroll-e2e5-session-page.png",
    });
  });
});
