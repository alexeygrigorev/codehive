import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchSubAgents } from "@/api/subagents";

describe("API: subagents", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchSubAgents calls the correct endpoint and returns SessionRead[]", async () => {
    const mockData = [
      {
        id: "sub-1",
        project_id: "p1",
        issue_id: null,
        parent_session_id: "session-1",
        name: "Backend Agent",
        engine: "claude",
        mode: "execution",
        status: "completed",
        config: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "sub-2",
        project_id: "p1",
        issue_id: null,
        parent_session_id: "session-1",
        name: "Frontend Agent",
        engine: "claude",
        mode: "execution",
        status: "executing",
        config: null,
        created_at: "2026-01-01T00:01:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchSubAgents("session-1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/sessions/session-1/subagents",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchSubAgents throws on 500 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchSubAgents("session-1")).rejects.toThrow(
      "Failed to fetch sub-agents: 500",
    );
  });

  it("fetchSubAgents throws on 404 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 404 }),
    );

    await expect(fetchSubAgents("session-1")).rejects.toThrow(
      "Failed to fetch sub-agents: 404",
    );
  });
});
