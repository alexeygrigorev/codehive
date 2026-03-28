import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchContextFiles,
  fetchContextFileContent,
} from "@/api/contextFiles";

describe("API: contextFiles", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchContextFiles() calls GET /api/projects/{id}/context-files", async () => {
    const mockData = [
      { path: "CLAUDE.md", size: 100 },
      { path: ".cursorrules", size: 50 },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchContextFiles("p1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/p1/context-files",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchContextFiles() throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchContextFiles("p1")).rejects.toThrow(
      "Failed to fetch context files: 500",
    );
  });

  it("fetchContextFileContent() calls GET with file path", async () => {
    const mockData = { path: "CLAUDE.md", content: "# Hello" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchContextFileContent("p1", "CLAUDE.md");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/projects/p1/context-files/CLAUDE.md",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchContextFileContent() throws on 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 404 }),
    );

    await expect(fetchContextFileContent("p1", "CLAUDE.md")).rejects.toThrow(
      "Failed to fetch context file: 404",
    );
  });
});
