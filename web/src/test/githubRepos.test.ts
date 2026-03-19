import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchGhStatus,
  fetchGhRepos,
  cloneRepo,
} from "@/api/githubRepos";

const mockGet = vi.fn();
const mockPost = vi.fn();

vi.mock("@/api/client", () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}));

function jsonResponse(data: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: () => Promise.resolve(data),
  };
}

describe("githubRepos API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("fetchGhStatus", () => {
    it("returns status on success", async () => {
      mockGet.mockResolvedValue(
        jsonResponse({
          available: true,
          authenticated: true,
          username: "testuser",
          error: null,
        }),
      );

      const result = await fetchGhStatus();
      expect(mockGet).toHaveBeenCalledWith("/api/github/status");
      expect(result.available).toBe(true);
      expect(result.username).toBe("testuser");
    });

    it("throws on non-ok response", async () => {
      mockGet.mockResolvedValue(jsonResponse(null, false, 500));
      await expect(fetchGhStatus()).rejects.toThrow("500");
    });
  });

  describe("fetchGhRepos", () => {
    it("fetches repos without params", async () => {
      mockGet.mockResolvedValue(
        jsonResponse({ repos: [], owner: "user", total: 0 }),
      );

      const result = await fetchGhRepos();
      expect(mockGet).toHaveBeenCalledWith("/api/github/repos");
      expect(result.total).toBe(0);
    });

    it("appends query params when provided", async () => {
      mockGet.mockResolvedValue(
        jsonResponse({ repos: [], owner: "org", total: 0 }),
      );

      await fetchGhRepos({ owner: "org", search: "test", limit: 50 });
      const url = mockGet.mock.calls[0][0] as string;
      expect(url).toContain("owner=org");
      expect(url).toContain("search=test");
      expect(url).toContain("limit=50");
    });

    it("throws on failure", async () => {
      mockGet.mockResolvedValue(jsonResponse(null, false, 502));
      await expect(fetchGhRepos()).rejects.toThrow("502");
    });
  });

  describe("cloneRepo", () => {
    it("returns clone response on success", async () => {
      mockPost.mockResolvedValue(
        jsonResponse({
          project_id: "uuid-123",
          project_name: "myrepo",
          path: "/tmp/myrepo",
          cloned: true,
        }),
      );

      const result = await cloneRepo({
        repo_url: "https://github.com/user/myrepo",
        destination: "/tmp/myrepo",
        project_name: "myrepo",
      });

      expect(mockPost).toHaveBeenCalledWith("/api/github/clone", {
        repo_url: "https://github.com/user/myrepo",
        destination: "/tmp/myrepo",
        project_name: "myrepo",
      });
      expect(result.cloned).toBe(true);
    });

    it("throws with detail on 409", async () => {
      mockPost.mockResolvedValue({
        ok: false,
        status: 409,
        json: () =>
          Promise.resolve({ detail: "Destination directory already exists" }),
      });

      await expect(
        cloneRepo({
          repo_url: "https://github.com/user/repo",
          destination: "/tmp/exists",
          project_name: "repo",
        }),
      ).rejects.toThrow("already exists");
    });

    it("throws generic message when no detail in response", async () => {
      mockPost.mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error("bad json")),
      });

      await expect(
        cloneRepo({
          repo_url: "https://github.com/user/repo",
          destination: "/tmp/x",
          project_name: "x",
        }),
      ).rejects.toThrow("Clone failed: 500");
    });
  });
});
