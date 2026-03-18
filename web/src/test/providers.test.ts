import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchProviders } from "@/api/providers";

describe("API: providers", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchProviders calls correct endpoint and returns parsed array", async () => {
    const mockData = [
      {
        name: "anthropic",
        base_url: "https://api.anthropic.com",
        api_key_set: true,
        default_model: "claude-sonnet-4-20250514",
      },
      {
        name: "zai",
        base_url: "https://api.z.ai/api/anthropic",
        api_key_set: false,
        default_model: "glm-4.7",
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
