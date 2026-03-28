import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchArchivedProjects,
  archiveProject,
  unarchiveProject,
  deleteProject,
} from "@/api/projects";
import { deleteSession } from "@/api/sessions";

describe("API: archive/delete projects", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchArchivedProjects() calls GET /api/projects/archived", async () => {
    const mockData = [
      {
        id: "p1",
        name: "Archived",
        path: "/tmp/archived",
        description: null,
        archetype: null,
        knowledge: null,
        created_at: "2026-01-01T00:00:00Z",
        archived_at: "2026-03-01T00:00:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchArchivedProjects();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/archived",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchArchivedProjects() throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchArchivedProjects()).rejects.toThrow(
      "Failed to fetch archived projects: 500",
    );
  });

  it("archiveProject(id) calls POST /api/projects/{id}/archive", async () => {
    const mockProject = {
      id: "p1",
      name: "Test",
      path: null,
      description: null,
      archetype: null,
      knowledge: null,
      created_at: "2026-01-01T00:00:00Z",
      archived_at: "2026-03-28T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockProject), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await archiveProject("p1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/p1/archive",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(result.archived_at).toBe("2026-03-28T00:00:00Z");
  });

  it("archiveProject(id) throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 404 }),
    );

    await expect(archiveProject("nonexistent")).rejects.toThrow(
      "Failed to archive project: 404",
    );
  });

  it("unarchiveProject(id) calls POST /api/projects/{id}/unarchive", async () => {
    const mockProject = {
      id: "p1",
      name: "Test",
      path: null,
      description: null,
      archetype: null,
      knowledge: null,
      created_at: "2026-01-01T00:00:00Z",
      archived_at: null,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockProject), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await unarchiveProject("p1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/p1/unarchive",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(result.archived_at).toBeNull();
  });

  it("deleteProject(id) calls DELETE /api/projects/{id}", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );

    await deleteProject("p1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/p1",
      expect.objectContaining({
        method: "DELETE",
      }),
    );
  });

  it("deleteProject(id) throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 404 }),
    );

    await expect(deleteProject("nonexistent")).rejects.toThrow(
      "Failed to delete project: 404",
    );
  });
});

describe("API: delete session", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("deleteSession(id) calls DELETE /api/sessions/{id}", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );

    await deleteSession("s1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/sessions/s1",
      expect.objectContaining({
        method: "DELETE",
      }),
    );
  });

  it("deleteSession(id) throws on 409 with meaningful message", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 409 }),
    );

    await expect(deleteSession("s1")).rejects.toThrow(
      "Cannot delete this session because it has sub-agent sessions",
    );
  });

  it("deleteSession(id) throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(deleteSession("s1")).rejects.toThrow(
      "Failed to delete session: 500",
    );
  });
});
