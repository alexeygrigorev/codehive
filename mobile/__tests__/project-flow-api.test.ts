import apiClient from "../src/api/client";
import {
  startFlow,
  respondToFlow,
  finalizeFlow,
} from "../src/api/projectFlow";

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

const mockPost = apiClient.post as jest.Mock;

beforeEach(() => {
  jest.clearAllMocks();
});

describe("api/projectFlow", () => {
  describe("startFlow", () => {
    it("calls POST /api/project-flow/start with correct body and returns parsed response", async () => {
      const mockResult = {
        flow_id: "flow-1",
        session_id: "sess-1",
        first_questions: [
          { id: "q1", text: "What is the project?", category: "General" },
        ],
      };
      mockPost.mockResolvedValue({ data: mockResult });

      const result = await startFlow({ flow_type: "brainstorm" });

      expect(mockPost).toHaveBeenCalledWith("/api/project-flow/start", {
        flow_type: "brainstorm",
      });
      expect(result).toEqual(mockResult);
    });

    it("passes initial_input when provided", async () => {
      mockPost.mockResolvedValue({
        data: { flow_id: "f1", session_id: "s1", first_questions: [] },
      });

      await startFlow({
        flow_type: "from_notes",
        initial_input: "my notes here",
      });

      expect(mockPost).toHaveBeenCalledWith("/api/project-flow/start", {
        flow_type: "from_notes",
        initial_input: "my notes here",
      });
    });

    it("propagates errors on failure", async () => {
      mockPost.mockRejectedValue(new Error("Network Error"));

      await expect(
        startFlow({ flow_type: "brainstorm" }),
      ).rejects.toThrow("Network Error");
    });
  });

  describe("respondToFlow", () => {
    it("calls POST /api/project-flow/{flowId}/respond with answers array", async () => {
      const mockResult = {
        next_questions: [
          { id: "q2", text: "Follow-up?", category: "Details" },
        ],
        brief: null,
      };
      mockPost.mockResolvedValue({ data: mockResult });

      const answers = [{ question_id: "q1", answer: "My answer" }];
      const result = await respondToFlow("flow-1", answers);

      expect(mockPost).toHaveBeenCalledWith(
        "/api/project-flow/flow-1/respond",
        { answers },
      );
      expect(result).toEqual(mockResult);
    });

    it("propagates errors on non-2xx responses", async () => {
      mockPost.mockRejectedValue(new Error("Request failed with status 500"));

      await expect(
        respondToFlow("flow-1", []),
      ).rejects.toThrow("Request failed with status 500");
    });
  });

  describe("finalizeFlow", () => {
    it("calls POST /api/project-flow/{flowId}/finalize and returns parsed result", async () => {
      const mockResult = {
        project_id: "proj-1",
        sessions: [{ id: "s1", name: "Setup", mode: "execution" }],
      };
      mockPost.mockResolvedValue({ data: mockResult });

      const result = await finalizeFlow("flow-1");

      expect(mockPost).toHaveBeenCalledWith(
        "/api/project-flow/flow-1/finalize",
      );
      expect(result).toEqual(mockResult);
    });

    it("propagates errors on failure", async () => {
      mockPost.mockRejectedValue(new Error("Request failed with status 400"));

      await expect(finalizeFlow("flow-1")).rejects.toThrow(
        "Request failed with status 400",
      );
    });
  });
});
