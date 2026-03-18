/**
 * Bug #120 regression tests: error events must be displayed in chat, not silently swallowed.
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ChatPanel from "@/components/ChatPanel";
import type { SessionEvent } from "@/api/websocket";

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

describe("Bug 120: error events displayed in chat", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("CHAT_EVENT_TYPES includes 'error' so useSessionEvents receives error events", () => {
    // If error is in the filter list, then when useSessionEvents returns an error event,
    // the ChatPanel should render it.
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "error", {
        content: "Z.ai provider not configured: missing API key",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);

    // The error message should be visible in the chat
    expect(
      screen.getByText("Z.ai provider not configured: missing API key"),
    ).toBeInTheDocument();
  });

  it("error events render with error styling (data-role='error')", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "error", {
        content: "Session not found. Call create_session first.",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);

    const errorBubble = screen.getByText(
      "Session not found. Call create_session first.",
    );
    expect(errorBubble).toBeInTheDocument();
    // Should be rendered inside a message bubble with error role
    const bubble = errorBubble.closest("[data-role]");
    expect(bubble).toHaveAttribute("data-role", "error");
  });

  it("error events appear alongside normal messages", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "message.created", {
        role: "user",
        content: "Hello",
      }),
      makeEvent("e2", "error", {
        content: "Something went wrong",
      }),
    ]);
    render(<ChatPanel sessionId="s1" />);

    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });
});
