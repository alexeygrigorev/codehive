import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/api/client", () => ({
  apiClient: {
    baseURL: "http://localhost:7433",
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import { apiClient } from "@/api/client";
import { fetchUsage, fetchUsageSummary, fetchSessionUsage } from "@/api/usage";

const mockGet = vi.mocked(apiClient.get);

function jsonResponse(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(data),
  } as Response;
}

describe("Usage API client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetchUsage calls correct endpoint without params", async () => {
    const mockData = {
      records: [],
      summary: {
        total_requests: 0,
        total_input_tokens: 0,
        total_output_tokens: 0,
        estimated_cost: 0,
      },
    };
    mockGet.mockResolvedValue(jsonResponse(mockData));

    const result = await fetchUsage();
    expect(mockGet).toHaveBeenCalledWith("/api/usage");
    expect(result).toEqual(mockData);
  });

  it("fetchUsage builds query string with params", async () => {
    mockGet.mockResolvedValue(
      jsonResponse({ records: [], summary: { total_requests: 0, total_input_tokens: 0, total_output_tokens: 0, estimated_cost: 0 } }),
    );

    await fetchUsage({ session_id: "abc", start_date: "2026-01-01" });
    expect(mockGet).toHaveBeenCalledWith(
      "/api/usage?session_id=abc&start_date=2026-01-01",
    );
  });

  it("fetchUsageSummary calls summary endpoint", async () => {
    const summaryData = {
      total_requests: 5,
      total_input_tokens: 10000,
      total_output_tokens: 5000,
      estimated_cost: 0.075,
    };
    mockGet.mockResolvedValue(jsonResponse(summaryData));

    const result = await fetchUsageSummary({ project_id: "p1" });
    expect(mockGet).toHaveBeenCalledWith(
      "/api/usage/summary?project_id=p1",
    );
    expect(result).toEqual(summaryData);
  });

  it("fetchSessionUsage calls session-specific endpoint", async () => {
    const summaryData = {
      total_requests: 2,
      total_input_tokens: 3000,
      total_output_tokens: 1500,
      estimated_cost: 0.03,
    };
    mockGet.mockResolvedValue(jsonResponse(summaryData));

    const result = await fetchSessionUsage("session-123");
    expect(mockGet).toHaveBeenCalledWith("/api/sessions/session-123/usage");
    expect(result).toEqual(summaryData);
  });

  it("fetchUsage throws on non-ok response", async () => {
    mockGet.mockResolvedValue({ ok: false, status: 500 } as Response);

    await expect(fetchUsage()).rejects.toThrow("Failed to fetch usage: 500");
  });
});
