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

  it("renders a message count badge when messageCount > 0", () => {
    const session = makeSession("sub-4", "Chat Agent", "executing", "s1");
    render(
      <MemoryRouter>
        <ul>
          <SubAgentNode
            session={session}
            allSessions={[session]}
            messageCount={3}
          />
        </ul>
      </MemoryRouter>,
    );

    const badge = document.querySelector(".message-count-badge");
    expect(badge).not.toBeNull();
    expect(badge!.textContent).toBe("3");
  });

  it("does not render a message count badge when messageCount is 0", () => {
    const session = makeSession("sub-5", "Quiet Agent", "idle", "s1");
    render(
      <MemoryRouter>
        <ul>
          <SubAgentNode
            session={session}
            allSessions={[session]}
            messageCount={0}
          />
        </ul>
      </MemoryRouter>,
    );

    const badge = document.querySelector(".message-count-badge");
    expect(badge).toBeNull();
  });

  it("does not render a message count badge when messageCount is undefined", () => {
    const session = makeSession("sub-6", "Default Agent", "idle", "s1");
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

    const badge = document.querySelector(".message-count-badge");
    expect(badge).toBeNull();
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

  it("renders an engine badge showing the engine type", () => {
    const session = makeSession("sub-7", "SWE Agent", "executing", "s1");
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

    const badge = document.querySelector(".engine-badge");
    expect(badge).not.toBeNull();
    expect(badge!.textContent).toBe("claude");
  });

  it("renders correct engine badge for claude_code engine", () => {
    const session = {
      ...makeSession("sub-8", "CC Agent", "idle", "s1"),
      engine: "claude_code",
    };
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

    const badge = document.querySelector(".engine-badge");
    expect(badge).not.toBeNull();
    expect(badge!.textContent).toBe("claude_code");
    expect(badge!.className).toContain("bg-orange-100");
  });

  it("renders correct engine badge for native engine", () => {
    const session = {
      ...makeSession("sub-9", "Native Agent", "idle", "s1"),
      engine: "native",
    };
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

    const badge = document.querySelector(".engine-badge");
    expect(badge).not.toBeNull();
    expect(badge!.textContent).toBe("native");
    expect(badge!.className).toContain("bg-green-100");
  });
});
