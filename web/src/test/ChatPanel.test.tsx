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
): SessionEvent {
  return {
    id,
    session_id: "s1",
    type,
    data,
    created_at: new Date().toISOString(),
  };
}

describe("ChatPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock scrollIntoView
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("renders empty state when no messages exist", () => {
    mockUseSessionEvents.mockReturnValue([]);
    render(<ChatPanel sessionId="s1" />);
    expect(
      screen.getByText("No messages yet. Start the conversation."),
    ).toBeInTheDocument();
  });

  it("renders MessageBubble components for message.created events", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "message.created", {
        role: "user",
        content: "Hello from user",
      }),
      makeEvent("e2", "message.created", {
        role: "assistant",
        content: "Hello from assistant",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByText("Hello from user")).toBeInTheDocument();
    expect(screen.getByText("Hello from assistant")).toBeInTheDocument();
  });

  it("renders ToolCallResult for tool.call.started events", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "tool.call.started", {
        call_id: "c1",
        tool_name: "read_file",
        input: "/path/to/file",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByText("read_file")).toBeInTheDocument();
    expect(screen.getByText("Running...")).toBeInTheDocument();
  });

  it("updates ToolCallResult when matching tool.call.finished arrives", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "tool.call.started", {
        call_id: "c1",
        tool_name: "read_file",
        input: "/path",
      }),
      makeEvent("e2", "tool.call.finished", {
        call_id: "c1",
        output: "file contents",
        is_error: false,
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByText("file contents")).toBeInTheDocument();
    expect(screen.queryByText("Running...")).not.toBeInTheDocument();
  });

  it("has a scrollable container", () => {
    mockUseSessionEvents.mockReturnValue([]);
    const { container } = render(<ChatPanel sessionId="s1" />);
    const scrollable = container.querySelector(".overflow-y-auto");
    expect(scrollable).toBeInTheDocument();
  });

  it("renders both messages and tool calls in order", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "message.created", {
        role: "user",
        content: "Run a command",
      }),
      makeEvent("e2", "tool.call.started", {
        call_id: "c1",
        tool_name: "exec",
      }),
      makeEvent("e3", "tool.call.finished", {
        call_id: "c1",
        output: "done",
        is_error: false,
      }),
      makeEvent("e4", "message.created", {
        role: "assistant",
        content: "Command completed",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByText("Run a command")).toBeInTheDocument();
    expect(screen.getByText("exec")).toBeInTheDocument();
    expect(screen.getByText("done")).toBeInTheDocument();
    expect(screen.getByText("Command completed")).toBeInTheDocument();
  });
});
