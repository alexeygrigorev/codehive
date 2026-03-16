import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchSessionDiffs } from "@/api/diffs";

describe("API: diffs", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchSessionDiffs calls the correct endpoint and returns parsed response", async () => {
    const mockData = {
      session_id: "s1",
      files: [
        {
          path: "src/auth.py",
          diff_text: "--- a/src/auth.py\n+++ b/src/auth.py\n",
          additions: 2,
          deletions: 1,
        },
      ],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchSessionDiffs("s1");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/sessions/s1/diffs",
    );
    expect(result).toEqual(mockData);
  });

  it("fetchSessionDiffs throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 404 }),
    );

    await expect(fetchSessionDiffs("nonexistent")).rejects.toThrow(
      "Failed to fetch session diffs: 404",
    );
  });
});
