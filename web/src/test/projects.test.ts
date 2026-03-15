import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchProjects, fetchProject } from "@/api/projects";

describe("API: projects", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchProjects() calls GET /api/projects and returns parsed array", async () => {
    const mockData = [
      {
        id: "p1",
        workspace_id: "w1",
        name: "Project One",
        path: "/tmp/p1",
        description: null,
        archetype: null,
        knowledge: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchProjects();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/projects",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchProjects() throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchProjects()).rejects.toThrow(
      "Failed to fetch projects: 500",
    );
  });

  it("fetchProject(id) calls GET /api/projects/{id} and returns parsed project", async () => {
    const mockProject = {
      id: "p1",
      workspace_id: "w1",
      name: "Project One",
      path: "/tmp/p1",
      description: "A project",
      archetype: "web",
      knowledge: null,
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockProject), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchProject("p1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/projects/p1",
    );
    expect(result).toEqual(mockProject);
  });

  it("fetchProject(id) throws on 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 404 }),
    );

    await expect(fetchProject("nonexistent")).rejects.toThrow(
      "Failed to fetch project: 404",
    );
  });
});
