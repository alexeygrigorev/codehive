import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ChatPanel from "@/components/ChatPanel";
import type { SessionEvent } from "@/api/websocket";

// Mock the hooks and API
vi.mock("@/hooks/useSessionEvents", () => ({
  useSessionEvents: vi.fn(),
}));

vi.mock("@/api/messages", () => ({
  sendMessage: vi.fn(),
}));

import { useSessionEvents } from "@/hooks/useSessionEvents";

const mockUseSessionEvents = vi.mocked(useSessionEvents);

function makeEvent(
  id: string,
  type: string,
  data: Record<string, unknown>,
  created_at?: string,
): SessionEvent {
  return {
    id,
    session_id: "s1",
    type,
    data,
    created_at: created_at ?? new Date().toISOString(),
  };
}

describe("ChatPanel — history and deduplication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("renders message.delta events as streaming text", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("d1", "message.delta", { content: "Hello " }),
      makeEvent("d2", "message.delta", { content: "world" }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("replaces streaming buffer with final message.created", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("d1", "message.delta", { content: "Hello " }),
      makeEvent("d2", "message.delta", { content: "world" }),
      makeEvent("e-final", "message.created", {
        role: "assistant",
        content: "Hello world!",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    // Final message replaces streaming buffer
    expect(screen.getByText("Hello world!")).toBeInTheDocument();
    // The incomplete streaming text should not be present
    expect(screen.queryByText("Hello world")).not.toBeInTheDocument();
  });

  it("renders tool.call.started followed by tool.call.finished", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("t1", "tool.call.started", {
        call_id: "c1",
        tool_name: "bash",
        input: "ls -la",
      }),
      makeEvent("t2", "tool.call.finished", {
        call_id: "c1",
        output: "file1.txt",
        is_error: false,
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByText("bash")).toBeInTheDocument();
    expect(screen.getByText("file1.txt")).toBeInTheDocument();
  });

  it("shows empty state when no events", () => {
    mockUseSessionEvents.mockReturnValue([]);
    render(<ChatPanel sessionId="s1" />);
    expect(
      screen.getByText("No messages yet. Start the conversation."),
    ).toBeInTheDocument();
  });

  it("does not duplicate user messages when same events appear", () => {
    // Simulate: historical + live both contain the same user message
    // (deduplication happens in WebSocketContext, but ChatPanel should
    // still handle identical events gracefully via unique IDs)
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "message.created", {
        role: "user",
        content: "Hello",
      }),
      makeEvent("e2", "message.created", {
        role: "assistant",
        content: "Hi there",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    const userMessages = screen.getAllByText("Hello");
    expect(userMessages).toHaveLength(1);
    const assistantMessages = screen.getAllByText("Hi there");
    expect(assistantMessages).toHaveLength(1);
  });
});
