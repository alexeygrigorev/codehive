import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import SubAgentNode from "@/components/SubAgentNode";

function makeSession(
  id: string,
  name: string,
  status: string,
  parentSessionId: string | null = null,
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

describe("SubAgentNode", () => {
  it("renders session name and status indicator with data-status attribute", () => {
    const session = makeSession("sub-1", "Backend Agent", "completed", "s1");
    render(
      <MemoryRouter>
        <ul>
          <SubAgentNode
            session={session}
            allSessions={[session]}
          />
        </ul>
      </MemoryRouter>,
    );

    expect(screen.getByText("Backend Agent")).toBeInTheDocument();
    const indicator = document.querySelector(".sub-agent-status");
    expect(indicator).not.toBeNull();
    expect(indicator!.getAttribute("data-status")).toBe("completed");
  });

  it("renders correct data-status for failed status", () => {
    const session = makeSession("sub-2", "Failing Agent", "failed", "s1");
    render(
      <MemoryRouter>
        <ul>
          <SubAgentNode
            session={session}
            allSessions={[session]}
          />
        </ul>
      </MemoryRouter>,
    );

    const indicator = document.querySelector(".sub-agent-status");
    expect(indicator!.getAttribute("data-status")).toBe("failed");
  });

  it("renders a link pointing to the correct session URL", () => {
    const session = makeSession("sub-3", "Test Agent", "idle", "s1");
    render(
      <MemoryRouter>
        <ul>
          <SubAgentNode
            session={session}
            allSessions={[session]}
          />
        </ul>
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: "Test Agent" });
    expect(link).toHaveAttribute("href", "/sessions/sub-3");
  });
});
