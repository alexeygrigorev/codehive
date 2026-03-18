import { test, expect } from "@playwright/test";
import { API_BASE } from "./e2e-constants";

test.describe("Context progress bar", () => {
  test("E2E 1: Context progress bar API returns valid data for a session", async ({ page, request }) => {
    // Create a project via API
    const projResp = await request.post(`${API_BASE}/api/projects`, {
      data: { name: "e2e-ctx-bar-project", path: "/tmp/e2e-ctx-bar-project" },
    });
    expect(projResp.ok()).toBeTruthy();
    const project = await projResp.json();

    // Create a session via API
    const sessResp = await request.post(
      `${API_BASE}/api/projects/${project.id}/sessions`,
      { data: { name: "e2e-ctx-bar-session", engine: "native", mode: "execution" } },
    );
    expect(sessResp.ok()).toBeTruthy();
    const session = await sessResp.json();

    // Verify the context endpoint returns valid JSON
    const ctxResp = await request.get(
      `${API_BASE}/api/sessions/${session.id}/context`,
    );
    expect(ctxResp.ok()).toBeTruthy();
    const data = await ctxResp.json();
    expect(data).toHaveProperty("used_tokens");
    expect(data).toHaveProperty("context_window");
    expect(data).toHaveProperty("usage_percent");
    expect(data).toHaveProperty("model");
    expect(data).toHaveProperty("estimated");
    expect(typeof data.used_tokens).toBe("number");
    expect(typeof data.context_window).toBe("number");
    expect(data.context_window).toBeGreaterThan(0);
    expect(data.used_tokens).toBe(0);
    expect(data.usage_percent).toBe(0.0);

    // Navigate to the session page
    await page.goto(`/sessions/${session.id}`);

    // Wait for the session header to be visible
    const header = page.getByTestId("session-header");
    await expect(header).toBeVisible({ timeout: 10_000 });

    await page.screenshot({ path: "/tmp/e2e-context-progress-bar.png", fullPage: true });
  });

  test("E2E 2: Context endpoint returns correct data with usage records", async ({ request }) => {
    // Create a project via API
    const projResp = await request.post(`${API_BASE}/api/projects`, {
      data: { name: "e2e-ctx-colors-project", path: "/tmp/e2e-ctx-colors-project" },
    });
    expect(projResp.ok()).toBeTruthy();
    const project = await projResp.json();

    // Create a session via API
    const sessResp = await request.post(
      `${API_BASE}/api/projects/${project.id}/sessions`,
      { data: { name: "e2e-ctx-colors-session", engine: "native", mode: "execution" } },
    );
    expect(sessResp.ok()).toBeTruthy();
    const session = await sessResp.json();

    // Verify context endpoint returns valid structure
    const ctxResp = await request.get(
      `${API_BASE}/api/sessions/${session.id}/context`,
    );
    expect(ctxResp.ok()).toBeTruthy();
    const data = await ctxResp.json();

    expect(typeof data.used_tokens).toBe("number");
    expect(typeof data.context_window).toBe("number");
    expect(typeof data.usage_percent).toBe("number");
    expect(typeof data.model).toBe("string");
    expect(typeof data.estimated).toBe("boolean");
    expect(data.context_window).toBe(200000);
  });
});
