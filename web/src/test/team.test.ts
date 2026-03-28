import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchTeam, generateTeam } from "@/api/team";

describe("API: team", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchTeam(projectId) calls GET /api/projects/{id}/team", async () => {
    const mockData = [
      {
        id: "a1",
        project_id: "p1",
        name: "Alice",
        role: "pm",
        avatar_seed: "Alice-p1",
        avatar_url: "https://api.dicebear.com/9.x/bottts-neutral/svg?seed=Alice-p1",
        personality: null,
        system_prompt_modifier: null,
        preferred_engine: null,
        preferred_model: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchTeam("p1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/p1/team",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchTeam(projectId) throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchTeam("p1")).rejects.toThrow(
      "Failed to fetch team: 500",
    );
  });

  it("generateTeam(projectId) calls POST /api/projects/{id}/team/generate and returns team", async () => {
    const mockTeam = [
      {
        id: "a1",
        project_id: "p1",
        name: "Alice",
        role: "pm",
        avatar_seed: "Alice-p1",
        avatar_url: "https://api.dicebear.com/9.x/bottts-neutral/svg?seed=Alice-p1",
        personality: null,
        system_prompt_modifier: null,
        preferred_engine: null,
        preferred_model: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockTeam), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await generateTeam("p1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/p1/team/generate",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({}),
      }),
    );
    expect(result).toEqual(mockTeam);
  });

  it("generateTeam(projectId) throws 'Team already exists' on 409", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Team already exists" }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(generateTeam("p1")).rejects.toThrow("Team already exists");
  });

  it("generateTeam(projectId) throws on other errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(generateTeam("p1")).rejects.toThrow(
      "Failed to generate team: 500",
    );
  });
});
