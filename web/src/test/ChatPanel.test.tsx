import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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

vi.mock("@/context/WebSocketContext", () => ({
  useWebSocket: vi.fn(() => ({
    injectEvents: vi.fn(),
  })),
}));

vi.mock("@/api/websocket", async () => {
  const actual = await vi.importActual("@/api/websocket");
  return {
    ...actual,
    normalizeEvent: vi.fn((e: Record<string, unknown>) => e),
  };
});

vi.mock("@/hooks/useVoiceInput", () => ({
  useVoiceInput: vi.fn(() => ({
    isListening: false,
    transcript: "",
    isSupported: false,
    startListening: vi.fn(),
    stopListening: vi.fn(),
    resetTranscript: vi.fn(),
  })),
}));

vi.mock("@/hooks/useAudioWaveform", () => ({
  useAudioWaveform: vi.fn(() => ({
    start: vi.fn(),
    stop: vi.fn(),
    waveformData: [],
    elapsedSeconds: 0,
  })),
}));

import { useSessionEvents } from "@/hooks/useSessionEvents";
import { sendMessage } from "@/api/messages";

const mockUseSessionEvents = vi.mocked(useSessionEvents);
const mockSendMessage = vi.mocked(sendMessage);

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

  it("calls onFirstMessage after first user message is sent", async () => {
    mockUseSessionEvents.mockReturnValue([]);
    mockSendMessage.mockResolvedValue([]);
    const onFirstMessage = vi.fn();

    render(
      <ChatPanel sessionId="s1" onFirstMessage={onFirstMessage} />,
    );

    const input = screen.getByLabelText("Message input");
    fireEvent.change(input, { target: { value: "Hello world" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(mockSendMessage).toHaveBeenCalledWith("s1", "Hello world");
    });
    expect(onFirstMessage).toHaveBeenCalledWith("Hello world");
  });

  it("does not call onFirstMessage on subsequent messages", async () => {
    mockUseSessionEvents.mockReturnValue([]);
    mockSendMessage.mockResolvedValue([]);
    const onFirstMessage = vi.fn();

    render(
      <ChatPanel sessionId="s1" onFirstMessage={onFirstMessage} />,
    );

    const input = screen.getByLabelText("Message input");

    // First message
    fireEvent.change(input, { target: { value: "First message" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(mockSendMessage).toHaveBeenCalledTimes(1);
    });
    expect(onFirstMessage).toHaveBeenCalledTimes(1);

    // Second message
    fireEvent.change(input, { target: { value: "Second message" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(mockSendMessage).toHaveBeenCalledTimes(2);
    });
    expect(onFirstMessage).toHaveBeenCalledTimes(1);
  });

  it("does not call onFirstMessage when session already has user messages", async () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "message.created", {
        role: "user",
        content: "Previous message",
      }),
    ]);
    mockSendMessage.mockResolvedValue([]);
    const onFirstMessage = vi.fn();

    render(
      <ChatPanel sessionId="s1" onFirstMessage={onFirstMessage} />,
    );

    const input = screen.getByLabelText("Message input");
    fireEvent.change(input, { target: { value: "New message" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(mockSendMessage).toHaveBeenCalledWith("s1", "New message");
    });
    expect(onFirstMessage).not.toHaveBeenCalled();
  });
});
