import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import SessionList from "@/components/SessionList";
import type { SessionRead } from "@/api/sessions";

function makeSession(overrides: Partial<SessionRead> = {}): SessionRead {
  return {
    id: "s1",
    project_id: "p1",
    issue_id: null,
    parent_session_id: null,
    name: "Test Session",
    engine: "claude",
    mode: "auto",
    status: "idle",
    config: null,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("SessionList", () => {
  it("renders a row for each session with name, status, mode", () => {
    const sessions = [
      makeSession({ id: "s1", name: "Session One", status: "idle", mode: "auto" }),
      makeSession({ id: "s2", name: "Session Two", status: "executing", mode: "manual" }),
    ];
    render(
      <MemoryRouter>
        <SessionList sessions={sessions} />
      </MemoryRouter>,
    );
    expect(screen.getByText("Session One")).toBeInTheDocument();
    expect(screen.getByText("Session Two")).toBeInTheDocument();
    expect(screen.getAllByText(/Mode:/)).toHaveLength(2);
  });

  it("shows empty state message when sessions array is empty", () => {
    render(
      <MemoryRouter>
        <SessionList sessions={[]} />
      </MemoryRouter>,
    );
    expect(screen.getByText("No sessions for this project.")).toBeInTheDocument();
  });

  it("each session row links to /sessions/{id}", () => {
    const sessions = [makeSession({ id: "xyz-789", name: "Linked Session" })];
    render(
      <MemoryRouter>
        <SessionList sessions={sessions} />
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: /linked session/i });
    expect(link).toHaveAttribute("href", "/sessions/xyz-789");
  });

  it("displays status with appropriate visual differentiation", () => {
    const sessions = [
      makeSession({ id: "s1", name: "Idle", status: "idle" }),
      makeSession({ id: "s2", name: "Exec", status: "executing" }),
      makeSession({ id: "s3", name: "Done", status: "completed" }),
    ];
    render(
      <MemoryRouter>
        <SessionList sessions={sessions} />
      </MemoryRouter>,
    );
    const idleBadge = screen.getByText("idle");
    const execBadge = screen.getByText("executing");
    const doneBadge = screen.getByText("completed");

    expect(idleBadge.className).toContain("bg-gray-100");
    expect(execBadge.className).toContain("bg-blue-100");
    expect(doneBadge.className).toContain("bg-green-100");
  });
});
