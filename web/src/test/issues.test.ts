import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchIssues, createIssue } from "@/api/issues";

describe("API: issues", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchIssues(projectId) calls correct endpoint and returns parsed array", async () => {
    const mockData = [
      {
        id: "i1",
        project_id: "p1",
        title: "Fix bug",
        description: null,
        status: "open",
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchIssues("p1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/p1/issues",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchIssues with status filter appends ?status= query param", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await fetchIssues("p1", "open");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/p1/issues?status=open",
    );
  });

  it("fetchIssues throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchIssues("p1")).rejects.toThrow(
      "Failed to fetch issues: 500",
    );
  });

  it("createIssue POSTs to correct endpoint and returns new issue", async () => {
    const newIssue = {
      id: "i2",
      project_id: "p1",
      title: "New feature",
      description: "Details here",
      status: "open",
      created_at: "2026-01-02T00:00:00Z",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(newIssue), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await createIssue("p1", {
      title: "New feature",
      description: "Details here",
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/p1/issues",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          title: "New feature",
          description: "Details here",
        }),
      }),
    );
    expect(result).toEqual(newIssue);
  });

  it("createIssue throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 400 }),
    );

    await expect(
      createIssue("p1", { title: "Bad issue" }),
    ).rejects.toThrow("Failed to create issue: 400");
  });
});
