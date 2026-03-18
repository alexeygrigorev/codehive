import { describe, it, expect, vi, beforeEach } from "vitest";
import { searchAll, searchSessionHistory } from "@/api/search";

describe("API: search", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("searchAll(query) calls GET /api/search?q=query", async () => {
    const mockData = { results: [], total: 0, has_more: false };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await searchAll("query");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/search?q=query",
    );
    expect(result).toEqual(mockData);
  });

  it("searchAll with type and limit includes them in query params", async () => {
    const mockData = { results: [], total: 0, has_more: false };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await searchAll("query", { type: "session", limit: 10 });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/search?q=query&type=session&limit=10",
    );
  });

  it("searchAll with offset includes offset in query params", async () => {
    const mockData = { results: [], total: 0, has_more: false };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await searchAll("test", { limit: 20, offset: 40 });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/search?q=test&limit=20&offset=40",
    );
  });

  it("searchAll throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(searchAll("query")).rejects.toThrow("Search failed: 500");
  });

  it("searchSessionHistory calls GET /api/sessions/{id}/history?q=query", async () => {
    const mockData = { results: [], total: 0 };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await searchSessionHistory("sess-1", "query");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/sessions/sess-1/history?q=query",
    );
    expect(result).toEqual(mockData);
  });

  it("searchSessionHistory throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 404 }),
    );

    await expect(searchSessionHistory("sess-1", "query")).rejects.toThrow(
      "Session history search failed: 404",
    );
  });
});
