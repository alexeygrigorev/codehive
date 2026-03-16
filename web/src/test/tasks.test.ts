import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchTasks } from "@/api/tasks";

describe("API: tasks", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchTasks calls the correct endpoint and returns typed TaskRead[]", async () => {
    const mockData = [
      {
        id: "t1",
        session_id: "s1",
        title: "Set up project",
        instructions: "Initialize the repo",
        status: "done",
        priority: 1,
        depends_on: [],
        mode: "execution",
        created_by: "agent",
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchTasks("s1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/sessions/s1/tasks",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchTasks throws on non-200 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchTasks("s1")).rejects.toThrow(
      "Failed to fetch tasks: 500",
    );
  });
});
