import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchEvents } from "@/api/events";

describe("API: events", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchEvents calls the correct endpoint and returns typed EventRead[]", async () => {
    const mockData = [
      {
        id: "e1",
        session_id: "s1",
        type: "task_started",
        data: { task_id: "t1" },
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchEvents("s1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/sessions/s1/events",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchEvents throws on non-200 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 403 }),
    );

    await expect(fetchEvents("s1")).rejects.toThrow(
      "Failed to fetch events: 403",
    );
  });
});
