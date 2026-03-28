import { test, expect } from "@playwright/test";
import { API_BASE } from "./e2e-constants";

const suffix = Date.now().toString(36);

async function createProject(name: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, path: `/tmp/e2e-role-${name}` }),
  });
  if (!res.ok) throw new Error(`Failed to create project: ${res.status}`);
  const data = (await res.json()) as { id: string };
  return data.id;
}

async function createSession(
  projectId: string,
  name: string,
  role: string | null,
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, engine: "claude_code", role }),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  const data = (await res.json()) as { id: string };
  return data.id;
}

test.describe("Role badge visibility", () => {
  let projectId: string;
  let pmSessionId: string;

  test.beforeAll(async () => {
    projectId = await createProject(`role-badge-${suffix}`);
    pmSessionId = await createSession(projectId, `PM Session ${suffix}`, "pm");
    await createSession(projectId, `Plain Session ${suffix}`, null);
  });

  test("project page shows role badge for PM session and no badge for null-role session", async ({
    page,
  }) => {
    await page.goto(`/projects/${projectId}`);

    // Wait for sessions to load
    await expect(
      page.getByText(`PM Session ${suffix}`),
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(`Plain Session ${suffix}`)).toBeVisible();

    // Screenshot: project page with sessions
    await page.screenshot({ path: "/tmp/role-badges-e2e-project.png" });

    // PM session row should have a role badge with text "PM"
    const pmRow = page.getByText(`PM Session ${suffix}`).locator("../..");
    const pmBadge = pmRow.locator('[data-testid="role-badge"]');
    await expect(pmBadge).toBeVisible();
    await expect(pmBadge).toHaveText("PM");

    // Plain session row should have no role badge
    const plainRow = page
      .getByText(`Plain Session ${suffix}`)
      .locator("../..");
    const plainBadge = plainRow.locator('[data-testid="role-badge"]');
    await expect(plainBadge).toHaveCount(0);
  });

  test("session detail page shows role badge in header for PM session", async ({
    page,
  }) => {
    await page.goto(`/sessions/${pmSessionId}`);

    // Wait for session to load
    await expect(page.getByText(`PM Session ${suffix}`)).toBeVisible({
      timeout: 10_000,
    });

    // Screenshot: session detail header
    await page.screenshot({ path: "/tmp/role-badges-e2e-session.png" });

    // Header should contain role badge
    const header = page.getByTestId("session-header");
    const badge = header.locator('[data-testid="role-badge"]');
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText("PM");
  });
});
