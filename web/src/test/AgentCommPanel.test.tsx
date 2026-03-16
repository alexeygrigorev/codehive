import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AgentCommPanel from "@/components/sidebar/AgentCommPanel";

vi.mock("@/api/agentComm", () => ({
  fetchAgentMessages: vi.fn(),
}));

import { fetchAgentMessages } from "@/api/agentComm";
const mockFetchAgentMessages = vi.mocked(fetchAgentMessages);

function makeEvent(
  id: string,
  type: "agent.message" | "agent.query",
  message: string,
  sender: string = "s2",
  target: string = "s1",
) {
  return {
    id,
    session_id: "s1",
    type,
    data: {
      sender_session_id: sender,
      target_session_id: target,
      message,
      timestamp: "2026-01-01T00:00:00Z",
    },
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("AgentCommPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while fetch is pending", () => {
    mockFetchAgentMessages.mockReturnValue(new Promise(() => {}));
    render(<AgentCommPanel sessionId="s1" />);
    expect(
      screen.getByText("Loading agent communications..."),
    ).toBeInTheDocument();
  });

  it("shows empty state when no agent comm events exist", async () => {
    mockFetchAgentMessages.mockResolvedValue([]);
    render(<AgentCommPanel sessionId="s1" />);

    await waitFor(() => {
      expect(
        screen.getByText("No agent communications"),
      ).toBeInTheDocument();
    });
  });

  it("renders all agent.message events when they exist", async () => {
    mockFetchAgentMessages.mockResolvedValue([
      makeEvent("e1", "agent.message", "hello there"),
      makeEvent("e2", "agent.message", "how are you"),
      makeEvent("e3", "agent.message", "all good"),
    ]);
    render(<AgentCommPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("hello there")).toBeInTheDocument();
    });
    expect(screen.getByText("how are you")).toBeInTheDocument();
    expect(screen.getByText("all good")).toBeInTheDocument();
  });

  it("renders both agent.message and agent.query events with correct data-type", async () => {
    mockFetchAgentMessages.mockResolvedValue([
      makeEvent("e1", "agent.message", "msg content"),
      makeEvent("e2", "agent.query", "query content"),
    ]);
    render(<AgentCommPanel sessionId="s1" />);

    await waitFor(() => {
      expect(screen.getByText("msg content")).toBeInTheDocument();
    });
    expect(screen.getByText("query content")).toBeInTheDocument();

    const items = document.querySelectorAll(".agent-message-item");
    const types = Array.from(items).map((el) => el.getAttribute("data-type"));
    expect(types).toContain("agent.message");
    expect(types).toContain("agent.query");
  });

  it("shows error message when fetch fails", async () => {
    mockFetchAgentMessages.mockRejectedValue(
      new Error("Failed to fetch agent messages: 500"),
    );
    render(<AgentCommPanel sessionId="s1" />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch agent messages: 500"),
      ).toBeInTheDocument();
    });
  });
});
