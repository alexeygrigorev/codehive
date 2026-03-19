import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
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

describe("ChatPanel - Subagent Events", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("renders SubAgentEventCard for subagent.spawned events", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "subagent.spawned", {
        child_name: "subagent-swe",
        child_session_id: "child-1",
        engine: "claude_code",
        mission: "Add health check endpoint",
      }),
    ]);
    render(
      <MemoryRouter>
        <ChatPanel sessionId="s1" />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Spawned sub-agent/)).toBeInTheDocument();
    expect(screen.getByText("subagent-swe")).toBeInTheDocument();
    expect(screen.getByText("claude_code")).toBeInTheDocument();
    expect(
      screen.getByText(/Mission: Add health check endpoint/),
    ).toBeInTheDocument();
  });

  it("renders SubAgentEventCard for subagent.report events", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "subagent.report", {
        child_name: "subagent-swe",
        child_session_id: "child-1",
        status: "completed",
        summary: "Added GET /health endpoint, 2 tests passing",
        files_changed: 2,
      }),
    ]);
    render(
      <MemoryRouter>
        <ChatPanel sessionId="s1" />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Sub-agent completed/)).toBeInTheDocument();
    expect(screen.getByText("subagent-swe")).toBeInTheDocument();
    expect(
      screen.getByText("Added GET /health endpoint, 2 tests passing"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Status: completed, 2 files changed/)).toBeInTheDocument();
  });

  it("renders subagent events interleaved with regular messages", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "message.created", {
        role: "user",
        content: "Start the agents",
      }),
      makeEvent("e2", "subagent.spawned", {
        child_name: "worker-1",
        engine: "native",
        mission: "Do the work",
      }),
      makeEvent("e3", "message.created", {
        role: "assistant",
        content: "Spawned a worker",
      }),
      makeEvent("e4", "subagent.report", {
        child_name: "worker-1",
        status: "completed",
        summary: "Work done",
      }),
    ]);
    render(
      <MemoryRouter>
        <ChatPanel sessionId="s1" />
      </MemoryRouter>,
    );

    expect(screen.getByText("Start the agents")).toBeInTheDocument();
    expect(screen.getByText(/Spawned sub-agent/)).toBeInTheDocument();
    expect(screen.getByText("Spawned a worker")).toBeInTheDocument();
    expect(screen.getByText(/Sub-agent completed/)).toBeInTheDocument();
  });

  it("spawned card has a clickable link to child session", () => {
    mockUseSessionEvents.mockReturnValue([
      makeEvent("e1", "subagent.spawned", {
        child_name: "linked-agent",
        child_session_id: "child-99",
        engine: "native",
        mission: "Linked mission",
      }),
    ]);
    render(
      <MemoryRouter>
        <ChatPanel sessionId="s1" />
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: "linked-agent" });
    expect(link).toHaveAttribute("href", "/sessions/child-99");
  });
});
