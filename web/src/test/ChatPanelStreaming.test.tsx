import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
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
import { useWebSocket } from "@/context/WebSocketContext";

const mockUseSessionEvents = vi.mocked(useSessionEvents);
const mockSendMessage = vi.mocked(sendMessage);
const mockUseWebSocket = vi.mocked(useWebSocket);

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

describe("ChatPanel Streaming", () => {
  let mockInjectEvents: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
    mockInjectEvents = vi.fn();
    mockUseWebSocket.mockReturnValue({
      injectEvents: mockInjectEvents,
      connectionState: "connected",
      events: [],
      onEvent: vi.fn(),
      removeListener: vi.fn(),
    });
  });

  it("shows thinking indicator when sending a message", async () => {
    mockUseSessionEvents.mockReturnValue([]);

    // Make sendMessage hang so we can observe the thinking state
    let resolveSend!: () => void;
    mockSendMessage.mockImplementation(() => {
      return new Promise<SessionEvent[]>((resolve) => {
        resolveSend = () => resolve([]);
      });
    });

    render(<ChatPanel sessionId="s1" />);

    // No thinking indicator initially
    expect(screen.queryByTestId("thinking-indicator")).not.toBeInTheDocument();

    // Send a message
    const input = screen.getByLabelText("Message input");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.click(screen.getByText("Send"));

    // Thinking indicator should appear
    await waitFor(() => {
      expect(screen.getByTestId("thinking-indicator")).toBeInTheDocument();
    });

    // Resolve the send
    await act(async () => {
      resolveSend();
    });

    // Thinking indicator should disappear after send completes
    await waitFor(() => {
      expect(screen.queryByTestId("thinking-indicator")).not.toBeInTheDocument();
    });
  });

  it("hides thinking indicator when first delta event arrives via onEvent callback", async () => {
    mockUseSessionEvents.mockReturnValue([]);

    let capturedOnEvent: ((event: SessionEvent) => void) | undefined;
    let resolveSend!: () => void;

    mockSendMessage.mockImplementation(
      (_sessionId: string, _content: string, onEvent?: (event: SessionEvent) => void) => {
        capturedOnEvent = onEvent;
        return new Promise<SessionEvent[]>((resolve) => {
          resolveSend = () => resolve([]);
        });
      },
    );

    render(<ChatPanel sessionId="s1" />);

    const input = screen.getByLabelText("Message input");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.click(screen.getByText("Send"));

    // Thinking indicator is visible
    await waitFor(() => {
      expect(screen.getByTestId("thinking-indicator")).toBeInTheDocument();
    });

    // Simulate a delta event arriving
    await act(async () => {
      capturedOnEvent?.(
        makeEvent("d1", "message.delta", { content: "Hi" }),
      );
    });

    // Thinking indicator should be gone
    await waitFor(() => {
      expect(screen.queryByTestId("thinking-indicator")).not.toBeInTheDocument();
    });

    // Clean up
    await act(async () => {
      resolveSend();
    });
  });

  it("hides thinking indicator when tool.call.started arrives", async () => {
    mockUseSessionEvents.mockReturnValue([]);

    let capturedOnEvent: ((event: SessionEvent) => void) | undefined;
    let resolveSend!: () => void;

    mockSendMessage.mockImplementation(
      (_sessionId: string, _content: string, onEvent?: (event: SessionEvent) => void) => {
        capturedOnEvent = onEvent;
        return new Promise<SessionEvent[]>((resolve) => {
          resolveSend = () => resolve([]);
        });
      },
    );

    render(<ChatPanel sessionId="s1" />);

    const input = screen.getByLabelText("Message input");
    fireEvent.change(input, { target: { value: "Read file" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(screen.getByTestId("thinking-indicator")).toBeInTheDocument();
    });

    // Simulate a tool call event arriving
    await act(async () => {
      capturedOnEvent?.(
        makeEvent("t1", "tool.call.started", {
          call_id: "c1",
          tool_name: "read_file",
        }),
      );
    });

    await waitFor(() => {
      expect(screen.queryByTestId("thinking-indicator")).not.toBeInTheDocument();
    });

    await act(async () => {
      resolveSend();
    });
  });

  it("injects events one-by-one during streaming", async () => {
    mockUseSessionEvents.mockReturnValue([]);

    let capturedOnEvent: ((event: SessionEvent) => void) | undefined;
    let resolveSend!: () => void;

    mockSendMessage.mockImplementation(
      (_sessionId: string, _content: string, onEvent?: (event: SessionEvent) => void) => {
        capturedOnEvent = onEvent;
        return new Promise<SessionEvent[]>((resolve) => {
          resolveSend = () => resolve([]);
        });
      },
    );

    render(<ChatPanel sessionId="s1" />);

    const input = screen.getByLabelText("Message input");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(mockSendMessage).toHaveBeenCalled();
    });

    // Simulate events arriving one-by-one
    const event1 = makeEvent("d1", "message.delta", { content: "Hi" });
    const event2 = makeEvent("d2", "message.delta", { content: " there" });

    await act(async () => {
      capturedOnEvent?.(event1);
    });
    expect(mockInjectEvents).toHaveBeenCalledWith([event1]);

    await act(async () => {
      capturedOnEvent?.(event2);
    });
    expect(mockInjectEvents).toHaveBeenCalledWith([event2]);

    // Each event injected individually
    expect(mockInjectEvents).toHaveBeenCalledTimes(2);

    await act(async () => {
      resolveSend();
    });
  });

  it("disables input and send button while sending", async () => {
    mockUseSessionEvents.mockReturnValue([]);

    let resolveSend!: () => void;
    mockSendMessage.mockImplementation(() => {
      return new Promise<SessionEvent[]>((resolve) => {
        resolveSend = () => resolve([]);
      });
    });

    render(<ChatPanel sessionId="s1" />);

    const input = screen.getByLabelText("Message input");
    const sendButton = screen.getByText("Send");

    expect(input).not.toBeDisabled();
    expect(sendButton).not.toBeDisabled();

    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByLabelText("Message input")).toBeDisabled();
      expect(screen.getByText("Send")).toBeDisabled();
    });

    await act(async () => {
      resolveSend();
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Message input")).not.toBeDisabled();
      expect(screen.getByText("Send")).not.toBeDisabled();
    });
  });
});
