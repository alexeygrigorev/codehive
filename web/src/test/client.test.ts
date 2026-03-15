import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient, healthCheck } from "@/api/client";

describe("API client", () => {
  it("has default base URL of http://localhost:8000", () => {
    expect(apiClient.baseURL).toBe("http://localhost:8000");
  });

  describe("healthCheck", () => {
    beforeEach(() => {
      vi.restoreAllMocks();
    });

    it("calls GET /api/health and returns parsed JSON", async () => {
      const mockResponse = { status: "healthy" };
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response(JSON.stringify(mockResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

      const result = await healthCheck();

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/health",
      );
      expect(result).toEqual(mockResponse);
    });

    it("throws on non-ok response", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response("", { status: 500 }),
      );

      await expect(healthCheck()).rejects.toThrow("Health check failed: 500");
    });
  });
});
