import { describe, it, expect, vi, beforeEach } from "vitest";
import { approveAction, rejectAction } from "@/api/approvals";

vi.mock("@/api/client", () => ({
  apiClient: {
    baseURL: "http://localhost:7433",
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

import { apiClient } from "@/api/client";

const mockPost = vi.mocked(apiClient.post);

describe("approvals API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("approveAction", () => {
    it("calls POST to the correct URL with action_id in the body", async () => {
      mockPost.mockResolvedValue(new Response("", { status: 200 }));

      await approveAction("sess-1", "act-42");

      expect(mockPost).toHaveBeenCalledWith("/api/sessions/sess-1/approve", {
        action_id: "act-42",
      });
    });

    it("throws on non-OK response", async () => {
      mockPost.mockResolvedValue(new Response("", { status: 500 }));

      await expect(approveAction("sess-1", "act-42")).rejects.toThrow(
        "Failed to approve action: 500",
      );
    });
  });

  describe("rejectAction", () => {
    it("calls POST to the correct URL with action_id in the body", async () => {
      mockPost.mockResolvedValue(new Response("", { status: 200 }));

      await rejectAction("sess-1", "act-42");

      expect(mockPost).toHaveBeenCalledWith("/api/sessions/sess-1/reject", {
        action_id: "act-42",
      });
    });

    it("throws on non-OK response", async () => {
      mockPost.mockResolvedValue(new Response("", { status: 404 }));

      await expect(rejectAction("sess-1", "act-42")).rejects.toThrow(
        "Failed to reject action: 404",
      );
    });
  });
});
