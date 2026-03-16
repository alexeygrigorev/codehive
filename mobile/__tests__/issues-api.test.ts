import apiClient from "../src/api/client";
import { listIssues, getIssue } from "../src/api/issues";

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

describe("api/issues", () => {
  it("listIssues calls GET /api/projects/{projectId}/issues", async () => {
    mockGet.mockResolvedValue({ data: [{ id: "i1", title: "Bug" }] });
    const result = await listIssues("project-uuid");
    expect(mockGet).toHaveBeenCalledWith(
      "/api/projects/project-uuid/issues",
      undefined
    );
    expect(result).toEqual([{ id: "i1", title: "Bug" }]);
  });

  it("listIssues passes status filter when provided", async () => {
    mockGet.mockResolvedValue({ data: [] });
    await listIssues("project-uuid", "open");
    expect(mockGet).toHaveBeenCalledWith(
      "/api/projects/project-uuid/issues",
      { params: { status: "open" } }
    );
  });

  it("getIssue calls GET /api/issues/{issueId}", async () => {
    mockGet.mockResolvedValue({
      data: { id: "i1", title: "Fix bug", status: "open" },
    });
    const result = await getIssue("i1");
    expect(mockGet).toHaveBeenCalledWith("/api/issues/i1");
    expect(result).toEqual({ id: "i1", title: "Fix bug", status: "open" });
  });
});
