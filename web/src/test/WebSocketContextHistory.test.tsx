import { render, screen, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  WebSocketProvider,
  useWebSocket,
} from "@/context/WebSocketContext.tsx";
import type { SessionEvent } from "@/api/websocket.ts";

// Mock fetchEvents
vi.mock("@/api/events.ts", () => ({
  fetchEvents: vi.fn(),
}));

import { fetchEvents } from "@/api/events.ts";

const mockFetchEvents = vi.mocked(fetchEvents);

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];

  url: string;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn(() => {
    this.onclose?.();
  });

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  simulateOpen(): void {
    this.onopen?.();
  }

  simulateMessage(data: string): void {
    this.onmessage?.({ data });
  }

  simulateClose(): void {
    this.onclose?.();
  }
}

function makeEvent(overrides: Partial<SessionEvent> = {}): SessionEvent {
  return {
    id: "evt-1",
    session_id: "sess-1",
    type: "message.created",
    data: { role: "assistant", content: "hello" },
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function TestConsumer() {
  const { events } = useWebSocket();
  return (
    <div>
      <span data-testid="event-count">{events.length}</span>
      {events.map((e, i) => (
        <span key={i} data-testid={`event-${i}-id`}>
          {e.id}
        </span>
      ))}
    </div>
  );
}

describe("WebSocketProvider — history loading", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
    mockFetchEvents.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads historical events on mount when sessionId is set", async () => {
    const historicalEvents = [
      makeEvent({ id: "h1", created_at: "2026-01-01T00:00:01Z" }),
      makeEvent({ id: "h2", created_at: "2026-01-01T00:00:02Z" }),
    ];
    mockFetchEvents.mockResolvedValue(historicalEvents);

    render(
      <WebSocketProvider sessionId="sess-1">
        <TestConsumer />
      </WebSocketProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("event-count").textContent).toBe("2");
    });

    expect(screen.getByTestId("event-0-id").textContent).toBe("h1");
    expect(screen.getByTestId("event-1-id").textContent).toBe("h2");
  });

  it("deduplicates events when live WS event has same id as historical", async () => {
    const historicalEvents = [
      makeEvent({ id: "h1", created_at: "2026-01-01T00:00:01Z" }),
    ];
    mockFetchEvents.mockResolvedValue(historicalEvents);

    render(
      <WebSocketProvider sessionId="sess-1">
        <TestConsumer />
      </WebSocketProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("event-count").textContent).toBe("1");
    });

    // Now send a live event with the SAME id
    act(() => {
      const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      ws.simulateOpen();
    });
    act(() => {
      const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      ws.simulateMessage(
        JSON.stringify(makeEvent({ id: "h1" })),
      );
    });

    // Should still be 1, not 2 (deduplicated)
    await waitFor(() => {
      expect(screen.getByTestId("event-count").textContent).toBe("1");
    });
  });

  it("appends new live events after historical events", async () => {
    const historicalEvents = [
      makeEvent({ id: "h1", created_at: "2026-01-01T00:00:01Z" }),
    ];
    mockFetchEvents.mockResolvedValue(historicalEvents);

    render(
      <WebSocketProvider sessionId="sess-1">
        <TestConsumer />
      </WebSocketProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("event-count").textContent).toBe("1");
    });

    // Send a new live event with different id
    act(() => {
      const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      ws.simulateOpen();
    });
    act(() => {
      const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      ws.simulateMessage(
        JSON.stringify(makeEvent({ id: "live-1" })),
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId("event-count").textContent).toBe("2");
    });

    expect(screen.getByTestId("event-0-id").textContent).toBe("h1");
    expect(screen.getByTestId("event-1-id").textContent).toBe("live-1");
  });

  it("gracefully handles fetchEvents failure", async () => {
    mockFetchEvents.mockRejectedValue(new Error("Network error"));
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    render(
      <WebSocketProvider sessionId="sess-1">
        <TestConsumer />
      </WebSocketProvider>,
    );

    // Wait for the rejected promise to be handled
    await waitFor(() => {
      expect(warnSpy).toHaveBeenCalledWith(
        "Failed to fetch session history:",
        expect.any(Error),
      );
    });

    // Should still show 0 events (no crash)
    expect(screen.getByTestId("event-count").textContent).toBe("0");

    // Live events still work
    act(() => {
      const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      ws.simulateOpen();
    });
    act(() => {
      const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      ws.simulateMessage(
        JSON.stringify(makeEvent({ id: "live-1" })),
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId("event-count").textContent).toBe("1");
    });

    warnSpy.mockRestore();
  });

  it("clears events and fetches new history when sessionId changes", async () => {
    const historyS1 = [makeEvent({ id: "s1-h1", session_id: "sess-1" })];
    const historyS2 = [makeEvent({ id: "s2-h1", session_id: "sess-2" })];

    mockFetchEvents
      .mockResolvedValueOnce(historyS1)
      .mockResolvedValueOnce(historyS2);

    const { rerender } = render(
      <WebSocketProvider sessionId="sess-1">
        <TestConsumer />
      </WebSocketProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("event-count").textContent).toBe("1");
    });
    expect(screen.getByTestId("event-0-id").textContent).toBe("s1-h1");

    // Switch session
    rerender(
      <WebSocketProvider sessionId="sess-2">
        <TestConsumer />
      </WebSocketProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("event-0-id").textContent).toBe("s2-h1");
    });
    expect(screen.getByTestId("event-count").textContent).toBe("1");
  });
});
