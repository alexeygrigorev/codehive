import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchDefaultDirectory, fetchDirectories } from "@/api/system";

// Mock the client module
vi.mock("@/api/client", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

import { apiClient } from "@/api/client";
const mockGet = vi.mocked(apiClient.get);

describe("system API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("fetchDefaultDirectory", () => {
    it("returns the default directory on success", async () => {
      mockGet.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({ default_directory: "/home/user/codehive/" }),
      } as Response);

      const result = await fetchDefaultDirectory();
      expect(result.default_directory).toBe("/home/user/codehive/");
      expect(mockGet).toHaveBeenCalledWith("/api/system/default-directory");
    });

    it("throws on failure", async () => {
      mockGet.mockResolvedValue({
        ok: false,
        status: 500,
      } as Response);

      await expect(fetchDefaultDirectory()).rejects.toThrow(
        "Failed to fetch default directory: 500",
      );
    });
  });

  describe("fetchDirectories", () => {
    it("returns directory listing on success", async () => {
      const mockData = {
        path: "/home/user",
        parent: "/home",
        directories: [
          { name: "codehive", path: "/home/user/codehive", has_git: false },
        ],
      };
      mockGet.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
      } as Response);

      const result = await fetchDirectories("/home/user");
      expect(result.directories).toHaveLength(1);
      expect(result.directories[0].name).toBe("codehive");
      expect(mockGet).toHaveBeenCalledWith(
        "/api/system/directories?path=%2Fhome%2Fuser",
      );
    });

    it("throws specific message for 403", async () => {
      mockGet.mockResolvedValue({
        ok: false,
        status: 403,
      } as Response);

      await expect(fetchDirectories("/etc")).rejects.toThrow(
        "Path is outside the home directory",
      );
    });

    it("throws specific message for 404", async () => {
      mockGet.mockResolvedValue({
        ok: false,
        status: 404,
      } as Response);

      await expect(fetchDirectories("/nonexistent")).rejects.toThrow(
        "Directory not found",
      );
    });
  });
});
