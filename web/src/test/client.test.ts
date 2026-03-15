import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient, healthCheck } from "@/api/client";

describe("API client", () => {
  it("has default base URL of http://localhost:8000", () => {
    expect(apiClient.baseURL).toBe("http://localhost:8000");
  });

  describe("post", () => {
    beforeEach(() => {
      vi.restoreAllMocks();
    });

    it("sends POST request with JSON body and correct Content-Type header", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      );

      await apiClient.post("/api/test", { key: "value" });

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/test",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ key: "value" }),
        },
      );
    });

    it("constructs URL from baseURL + path", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response("", { status: 200 }),
      );

      await apiClient.post("/api/sessions/s1/messages", { content: "hi" });

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/sessions/s1/messages",
        expect.objectContaining({ method: "POST" }),
      );
    });
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
