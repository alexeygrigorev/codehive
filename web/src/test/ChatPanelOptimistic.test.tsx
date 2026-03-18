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

describe("ChatPanel Optimistic User Message", () => {
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

  it("injects optimistic user message before calling sendMessage", async () => {
    mockUseSessionEvents.mockReturnValue([]);

    let resolveSend!: () => void;
    mockSendMessage.mockImplementation(() => {
      return new Promise<SessionEvent[]>((resolve) => {
        resolveSend = () => resolve([]);
      });
    });

    render(<ChatPanel sessionId="s1" />);

    const input = screen.getByLabelText("Message input");
    fireEvent.change(input, { target: { value: "Hello optimistic" } });
    fireEvent.click(screen.getByText("Send"));

    // The first call to injectEvents should be the optimistic user message
    await waitFor(() => {
      expect(mockInjectEvents).toHaveBeenCalled();
    });

    const firstCall = mockInjectEvents.mock.calls[0][0] as SessionEvent[];
    expect(firstCall).toHaveLength(1);
    expect(firstCall[0].type).toBe("message.created");
    expect(firstCall[0].data.role).toBe("user");
    expect(firstCall[0].data.content).toBe("Hello optimistic");
    expect(firstCall[0].id).toMatch(/^optimistic-/);

    // sendMessage should also have been called
    expect(mockSendMessage).toHaveBeenCalledWith(
      "s1",
      "Hello optimistic",
      expect.any(Function),
    );

    await act(async () => {
      resolveSend();
    });
  });

  it("skips server user message echo to prevent duplicates", async () => {
    mockUseSessionEvents.mockReturnValue([]);

    let capturedOnEvent: ((event: SessionEvent) => void) | undefined;
    let resolveSend!: () => void;

    mockSendMessage.mockImplementation(
      (
        _sessionId: string,
        _content: string,
        onEvent?: (event: SessionEvent) => void,
      ) => {
        capturedOnEvent = onEvent;
        return new Promise<SessionEvent[]>((resolve) => {
          resolveSend = () => resolve([]);
        });
      },
    );

    render(<ChatPanel sessionId="s1" />);

    const input = screen.getByLabelText("Message input");
    fireEvent.change(input, { target: { value: "Test dedup" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(mockSendMessage).toHaveBeenCalled();
    });

    // Record inject calls count after the optimistic injection
    const callsAfterOptimistic = mockInjectEvents.mock.calls.length;

    // Simulate the server echoing back the user message
    await act(async () => {
      capturedOnEvent?.(
        makeEvent("server-user-1", "message.created", {
          role: "user",
          content: "Test dedup",
        }),
      );
    });

    // The server user echo should NOT have been injected
    expect(mockInjectEvents.mock.calls.length).toBe(callsAfterOptimistic);

    // But a non-user event should still be injected
    await act(async () => {
      capturedOnEvent?.(
        makeEvent("d1", "message.delta", { content: "Response" }),
      );
    });

    expect(mockInjectEvents.mock.calls.length).toBe(
      callsAfterOptimistic + 1,
    );

    await act(async () => {
      resolveSend();
    });
  });

  it("shows thinking indicator alongside optimistic user message", async () => {
    mockUseSessionEvents.mockReturnValue([]);

    let resolveSend!: () => void;
    mockSendMessage.mockImplementation(() => {
      return new Promise<SessionEvent[]>((resolve) => {
        resolveSend = () => resolve([]);
      });
    });

    render(<ChatPanel sessionId="s1" />);

    // Placeholder visible initially
    expect(
      screen.getByText("No messages yet. Start the conversation."),
    ).toBeInTheDocument();

    const input = screen.getByLabelText("Message input");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.click(screen.getByText("Send"));

    // Thinking indicator should appear
    await waitFor(() => {
      expect(screen.getByTestId("thinking-indicator")).toBeInTheDocument();
    });

    // Optimistic message was injected
    expect(mockInjectEvents).toHaveBeenCalled();
    const firstCall = mockInjectEvents.mock.calls[0][0] as SessionEvent[];
    expect(firstCall[0].data.role).toBe("user");

    await act(async () => {
      resolveSend();
    });
  });

  it("allows assistant message.created events through the filter", async () => {
    mockUseSessionEvents.mockReturnValue([]);

    let capturedOnEvent: ((event: SessionEvent) => void) | undefined;
    let resolveSend!: () => void;

    mockSendMessage.mockImplementation(
      (
        _sessionId: string,
        _content: string,
        onEvent?: (event: SessionEvent) => void,
      ) => {
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

    const callsAfterOptimistic = mockInjectEvents.mock.calls.length;

    // Simulate assistant message.created -- should NOT be filtered
    await act(async () => {
      capturedOnEvent?.(
        makeEvent("a1", "message.created", {
          role: "assistant",
          content: "Hi there",
        }),
      );
    });

    expect(mockInjectEvents.mock.calls.length).toBe(
      callsAfterOptimistic + 1,
    );

    await act(async () => {
      resolveSend();
    });
  });
});
