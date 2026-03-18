import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchSessions, updateSession } from "@/api/sessions";

describe("API: sessions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchSessions(projectId) calls correct endpoint and returns parsed array", async () => {
    const mockData = [
      {
        id: "s1",
        project_id: "p1",
        issue_id: null,
        parent_session_id: null,
        name: "Session One",
        engine: "claude",
        mode: "auto",
        status: "idle",
        config: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchSessions("p1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/p1/sessions",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchSessions(projectId) throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchSessions("p1")).rejects.toThrow(
      "Failed to fetch sessions: 500",
    );
  });

  it("updateSession calls PATCH endpoint with body", async () => {
    const mockData = {
      id: "s1",
      project_id: "p1",
      issue_id: null,
      parent_session_id: null,
      name: "Renamed",
      engine: "native",
      mode: "execution",
      status: "idle",
      config: null,
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await updateSession("s1", { name: "Renamed" });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/sessions/s1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ name: "Renamed" }),
      }),
    );
    expect(result).toEqual(mockData);
  });

  it("updateSession throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(updateSession("s1", { name: "Renamed" })).rejects.toThrow(
      "Failed to update session: 500",
    );
  });
});
