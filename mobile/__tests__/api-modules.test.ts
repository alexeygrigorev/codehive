import apiClient from "../src/api/client";
import { listProjects, getProject } from "../src/api/projects";
import { listSessions, getSession, sendMessage } from "../src/api/sessions";
import { listQuestions, answerQuestion } from "../src/api/questions";
import {
  listPendingApprovals,
  approve,
  reject,
} from "../src/api/approvals";

// Mock the axios client
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
const mockPost = apiClient.post as jest.Mock;

beforeEach(() => {
  jest.clearAllMocks();
});

describe("api/projects", () => {
  it("listProjects calls GET /api/projects", async () => {
    mockGet.mockResolvedValue({ data: [{ id: "1", name: "Project 1" }] });
    const result = await listProjects();
    expect(mockGet).toHaveBeenCalledWith("/api/projects");
    expect(result).toEqual([{ id: "1", name: "Project 1" }]);
  });

  it("getProject calls GET /api/projects/{id}", async () => {
    mockGet.mockResolvedValue({ data: { id: "uuid", name: "My Project" } });
    const result = await getProject("uuid");
    expect(mockGet).toHaveBeenCalledWith("/api/projects/uuid");
    expect(result).toEqual({ id: "uuid", name: "My Project" });
  });
});

describe("api/sessions", () => {
  it("listSessions calls GET /api/projects/{projectId}/sessions", async () => {
    mockGet.mockResolvedValue({ data: [] });
    await listSessions("project-uuid");
    expect(mockGet).toHaveBeenCalledWith(
      "/api/projects/project-uuid/sessions"
    );
  });

  it("getSession calls GET /api/sessions/{id}", async () => {
    mockGet.mockResolvedValue({ data: { id: "s1" } });
    await getSession("s1");
    expect(mockGet).toHaveBeenCalledWith("/api/sessions/s1");
  });

  it("sendMessage calls POST /api/sessions/{id}/messages with content", async () => {
    mockPost.mockResolvedValue({ data: { ok: true } });
    await sendMessage("session-uuid", "hello");
    expect(mockPost).toHaveBeenCalledWith(
      "/api/sessions/session-uuid/messages",
      { content: "hello" }
    );
  });
});

describe("api/questions", () => {
  it("listQuestions calls GET /api/questions", async () => {
    mockGet.mockResolvedValue({ data: [] });
    await listQuestions();
    expect(mockGet).toHaveBeenCalledWith("/api/questions");
  });

  it("answerQuestion calls POST /api/questions/{id}/answer", async () => {
    mockPost.mockResolvedValue({ data: { ok: true } });
    await answerQuestion("q-uuid", "yes");
    expect(mockPost).toHaveBeenCalledWith("/api/questions/q-uuid/answer", {
      answer: "yes",
    });
  });
});

describe("api/approvals", () => {
  it("listPendingApprovals calls GET /api/approvals", async () => {
    mockGet.mockResolvedValue({ data: [] });
    await listPendingApprovals();
    expect(mockGet).toHaveBeenCalledWith("/api/approvals");
  });

  it("approve calls POST /api/approvals/{id}/approve", async () => {
    mockPost.mockResolvedValue({ data: { ok: true } });
    await approve("a-uuid");
    expect(mockPost).toHaveBeenCalledWith("/api/approvals/a-uuid/approve");
  });

  it("reject calls POST /api/approvals/{id}/reject", async () => {
    mockPost.mockResolvedValue({ data: { ok: true } });
    await reject("a-uuid");
    expect(mockPost).toHaveBeenCalledWith("/api/approvals/a-uuid/reject");
  });
});
