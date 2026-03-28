import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchProviders } from "@/api/providers";

describe("API: providers", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchProviders calls correct endpoint and returns parsed array", async () => {
    const mockData = [
      {
        name: "claude",
        type: "cli",
        available: true,
        reason: "",
        models: [
          { id: "claude-sonnet-4-6", name: "Claude Sonnet 4.6", is_default: true },
          { id: "claude-opus-4-6", name: "Claude Opus 4.6", is_default: false },
        ],
      },
      {
        name: "zai",
        type: "api",
        available: false,
        reason: "API key not set",
        models: [
          { id: "claude-sonnet-4-6", name: "Claude Sonnet 4.6", is_default: true },
          { id: "claude-opus-4-6", name: "Claude Opus 4.6", is_default: false },
        ],
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await fetchProviders();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/providers",
    );
    expect(result).toEqual(mockData);
    expect(result[0].models).toHaveLength(2);
    expect(result[0].models[0].is_default).toBe(true);
  });

  it("fetchProviders throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("", { status: 500 }),
    );

    await expect(fetchProviders()).rejects.toThrow(
      "Failed to fetch providers: 500",
    );
  });
});
