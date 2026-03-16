import apiClient from "../src/api/client";
import { searchAll } from "../src/api/search";

jest.mock("../src/api/client", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    defaults: { baseURL: "http://10.0.2.2:7433" },
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  },
  DEFAULT_BASE_URL: "http://10.0.2.2:7433",
  STORAGE_KEYS: { BASE_URL: "codehive_base_url" },
}));

const mockGet = apiClient.get as jest.Mock;

beforeEach(() => {
  jest.clearAllMocks();
});

describe("api/search", () => {
  it("searchAll calls GET /api/search?q=test and returns parsed response", async () => {
    const mockResponse = {
      results: [{ id: "1", type: "session", snippet: "test result" }],
      total: 1,
      has_more: false,
    };
    mockGet.mockResolvedValue({ data: mockResponse });

    const result = await searchAll("test");

    expect(mockGet).toHaveBeenCalledWith("/api/search", {
      params: { q: "test" },
    });
    expect(result).toEqual(mockResponse);
  });

  it("searchAll with type filter includes type param", async () => {
    mockGet.mockResolvedValue({
      data: { results: [], total: 0, has_more: false },
    });

    await searchAll("test", { type: "session" });

    expect(mockGet).toHaveBeenCalledWith("/api/search", {
      params: { q: "test", type: "session" },
    });
  });

  it("searchAll with project_id and limit includes those params", async () => {
    mockGet.mockResolvedValue({
      data: { results: [], total: 0, has_more: false },
    });

    await searchAll("test", { project_id: "abc", limit: 10 });

    expect(mockGet).toHaveBeenCalledWith("/api/search", {
      params: { q: "test", project_id: "abc", limit: 10 },
    });
  });

  it("API error propagates as thrown error", async () => {
    mockGet.mockRejectedValue(new Error("Network Error"));

    await expect(searchAll("test")).rejects.toThrow("Network Error");
  });
});
