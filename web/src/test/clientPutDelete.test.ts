import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient } from "@/api/client";

describe("API client put and delete", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("put sends PUT request with JSON body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await apiClient.put("/api/test", { key: "value" });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/test",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: "value" }),
      },
    );
  });

  it("delete sends DELETE request", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 200 }),
    );

    await apiClient.delete("/api/test/123");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:7433/api/test/123",
      {
        method: "DELETE",
      },
    );
  });
});
