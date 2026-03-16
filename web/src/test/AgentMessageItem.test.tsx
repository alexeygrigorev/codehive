import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import AgentMessageItem from "@/components/AgentMessageItem";
import type { AgentCommEvent } from "@/api/agentComm";

function makeEvent(
  type: "agent.message" | "agent.query",
  sender: string,
  target: string,
  message: string,
  timestamp: string = "2026-01-15T14:30:00Z",
): AgentCommEvent {
  return {
    id: "e1",
    session_id: "s1",
    type,
    data: {
      sender_session_id: sender,
      target_session_id: target,
      message,
      timestamp,
    },
    created_at: timestamp,
  };
}

describe("AgentMessageItem", () => {
  it("renders agent.message with data-type attribute and message text when session is target", () => {
    const event = makeEvent("agent.message", "s2", "s1", "Hello from s2");
    render(<AgentMessageItem event={event} sessionId="s1" />);

    expect(screen.getByText("Hello from s2")).toBeInTheDocument();
    const item = document.querySelector(".agent-message-item");
    expect(item).not.toBeNull();
    expect(item!.getAttribute("data-type")).toBe("agent.message");
  });

  it("applies outgoing styling when session is the sender", () => {
    const event = makeEvent("agent.message", "s1", "s2", "Outgoing msg");
    render(<AgentMessageItem event={event} sessionId="s1" />);

    const item = document.querySelector(".agent-message-item");
    expect(item!.className).toContain("ml-auto");
    expect(item!.className).toContain("bg-blue-100");
  });

  it("renders agent.query with data-type attribute and query label", () => {
    const event = makeEvent("agent.query", "s2", "s1", "What is the status?");
    render(<AgentMessageItem event={event} sessionId="s1" />);

    expect(screen.getByText("What is the status?")).toBeInTheDocument();
    const item = document.querySelector(".agent-message-item");
    expect(item!.getAttribute("data-type")).toBe("agent.query");
    expect(screen.getByText("query")).toBeInTheDocument();
  });

  it("displays a human-readable timestamp", () => {
    const event = makeEvent(
      "agent.message",
      "s2",
      "s1",
      "timestamped msg",
      "2026-01-15T14:30:00Z",
    );
    render(<AgentMessageItem event={event} sessionId="s1" />);

    const timeEl = document.querySelector(".agent-message-time");
    expect(timeEl).not.toBeNull();
    // The formatted time should contain some digits (locale-dependent)
    expect(timeEl!.textContent).toMatch(/\d/);
  });
});
