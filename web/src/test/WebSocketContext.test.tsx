import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { WebSocketProvider, useWebSocket } from "@/context/WebSocketContext.tsx";
import type { SessionEvent } from "@/api/websocket.ts";

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
    data: {},
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function TestConsumer() {
  const { connectionState, events } = useWebSocket();
  return (
    <div>
      <span data-testid="state">{connectionState}</span>
      <span data-testid="event-count">{events.length}</span>
      {events.map((e, i) => (
        <span key={i} data-testid={`event-${i}`}>
          {e.type}
        </span>
      ))}
    </div>
  );
}

describe("WebSocketProvider", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a WebSocket connection when mounted with a sessionId", () => {
    render(
      <WebSocketProvider sessionId="sess-1">
        <TestConsumer />
      </WebSocketProvider>,
    );

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe(
      "ws://localhost:7433/api/sessions/sess-1/ws",
    );
  });

  it("closes the WebSocket connection on unmount", () => {
    const { unmount } = render(
      <WebSocketProvider sessionId="sess-1">
        <TestConsumer />
      </WebSocketProvider>,
    );

    const ws = MockWebSocket.instances[0];
    unmount();

    expect(ws.close).toHaveBeenCalled();
  });

  it("closes old and opens new connection when sessionId changes", () => {
    const { rerender } = render(
      <WebSocketProvider sessionId="sess-1">
        <TestConsumer />
      </WebSocketProvider>,
    );

    const ws1 = MockWebSocket.instances[0];

    rerender(
      <WebSocketProvider sessionId="sess-2">
        <TestConsumer />
      </WebSocketProvider>,
    );

    expect(ws1.close).toHaveBeenCalled();
    // The cleanup disconnect + the new connect may produce 2 new instances
    const lastWs = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    expect(lastWs.url).toBe("ws://localhost:7433/api/sessions/sess-2/ws");
  });

  it("child components receive connection state via useWebSocket", () => {
    render(
      <WebSocketProvider sessionId="sess-1">
        <TestConsumer />
      </WebSocketProvider>,
    );

    // Initially connecting
    expect(screen.getByTestId("state").textContent).toBe("connecting");

    // Simulate open
    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    expect(screen.getByTestId("state").textContent).toBe("connected");
  });

  it("child components receive events via useWebSocket", () => {
    render(
      <WebSocketProvider sessionId="sess-1">
        <TestConsumer />
      </WebSocketProvider>,
    );

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    act(() => {
      MockWebSocket.instances[0].simulateMessage(
        JSON.stringify(makeEvent({ type: "task.started" })),
      );
    });

    expect(screen.getByTestId("event-count").textContent).toBe("1");
    expect(screen.getByTestId("event-0").textContent).toBe("task.started");
  });

  it("useWebSocket throws when used outside provider", () => {
    // Suppress React error boundary console output
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => render(<TestConsumer />)).toThrow(
      "useWebSocket must be used within a WebSocketProvider",
    );

    spy.mockRestore();
  });
});
