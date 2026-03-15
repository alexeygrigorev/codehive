import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import SubAgentPanel from "@/components/sidebar/SubAgentPanel";

vi.mock("@/api/subagents", () => ({
  fetchSubAgents: vi.fn(),
}));

import { fetchSubAgents } from "@/api/subagents";
const mockFetchSubAgents = vi.mocked(fetchSubAgents);

function makeSession(
  id: string,
  name: string,
  status: string,
  parentSessionId: string,
) {
  return {
    id,
    project_id: "p1",
    issue_id: null,
    parent_session_id: parentSessionId,
    name,
    engine: "claude",
    mode: "execution",
    status,
    config: null,
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("SubAgentPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while fetch is pending", () => {
    mockFetchSubAgents.mockReturnValue(new Promise(() => {}));
    render(
      <MemoryRouter>
        <SubAgentPanel sessionId="s1" />
      </MemoryRouter>,
    );
    expect(screen.getByText("Loading sub-agents...")).toBeInTheDocument();
  });

  it("shows empty state when no sub-agents exist", async () => {
    mockFetchSubAgents.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <SubAgentPanel sessionId="s1" />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("No sub-agents")).toBeInTheDocument();
    });
  });

  it("renders all sub-agent names when sub-agents exist", async () => {
    mockFetchSubAgents.mockResolvedValue([
      makeSession("sub-1", "Backend Agent", "completed", "s1"),
      makeSession("sub-2", "Frontend Agent", "executing", "s1"),
      makeSession("sub-3", "Test Agent", "idle", "s1"),
    ]);
    render(
      <MemoryRouter>
        <SubAgentPanel sessionId="s1" />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Backend Agent")).toBeInTheDocument();
    });
    expect(screen.getByText("Frontend Agent")).toBeInTheDocument();
    expect(screen.getByText("Test Agent")).toBeInTheDocument();
  });

  it("shows error message when fetch fails", async () => {
    mockFetchSubAgents.mockRejectedValue(
      new Error("Failed to fetch sub-agents: 500"),
    );
    render(
      <MemoryRouter>
        <SubAgentPanel sessionId="s1" />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText("Failed to fetch sub-agents: 500"),
      ).toBeInTheDocument();
    });
  });

  it("shows aggregated progress with correct counts", async () => {
    mockFetchSubAgents.mockResolvedValue([
      makeSession("sub-1", "Agent A", "completed", "s1"),
      makeSession("sub-2", "Agent B", "executing", "s1"),
    ]);
    render(
      <MemoryRouter>
        <SubAgentPanel sessionId="s1" />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("1/2 completed")).toBeInTheDocument();
    });
  });
});
