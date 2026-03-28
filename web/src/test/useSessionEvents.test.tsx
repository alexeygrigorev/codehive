import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { WebSocketProvider } from "@/context/WebSocketContext.tsx";
import { useSessionEvents } from "@/hooks/useSessionEvents.ts";
import type { SessionEvent } from "@/api/websocket.ts";

// Mock fetchMessages used by WebSocketContext for history loading
vi.mock("@/api/messages.ts", () => ({
  fetchMessages: vi.fn().mockResolvedValue([]),
  sendMessage: vi.fn(),
}));

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

function EventConsumer({ typeFilter }: { typeFilter?: string[] }) {
  const events = useSessionEvents(typeFilter);
  return (
    <div>
      <span data-testid="count">{events.length}</span>
      {events.map((e, i) => (
        <span key={i} data-testid={`type-${i}`}>
          {e.type}
        </span>
      ))}
    </div>
  );
}

describe("useSessionEvents", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns an empty array initially", () => {
    render(
      <WebSocketProvider sessionId="sess-1">
        <EventConsumer />
      </WebSocketProvider>,
    );

    expect(screen.getByTestId("count").textContent).toBe("0");
  });

  it("accumulates events as they arrive", () => {
    render(
      <WebSocketProvider sessionId="sess-1">
        <EventConsumer />
      </WebSocketProvider>,
    );

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateOpen());

    act(() => {
      ws.simulateMessage(JSON.stringify(makeEvent({ id: "e1", type: "message.created" })));
    });
    act(() => {
      ws.simulateMessage(JSON.stringify(makeEvent({ id: "e2", type: "task.started" })));
    });

    expect(screen.getByTestId("count").textContent).toBe("2");
  });

  it("filters events by type when typeFilter is provided", () => {
    render(
      <WebSocketProvider sessionId="sess-1">
        <EventConsumer typeFilter={["message.created"]} />
      </WebSocketProvider>,
    );

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateOpen());

    act(() => {
      ws.simulateMessage(JSON.stringify(makeEvent({ id: "e1", type: "message.created" })));
    });
    act(() => {
      ws.simulateMessage(JSON.stringify(makeEvent({ id: "e2", type: "task.started" })));
    });
    act(() => {
      ws.simulateMessage(JSON.stringify(makeEvent({ id: "e3", type: "message.created" })));
    });

    expect(screen.getByTestId("count").textContent).toBe("2");
    expect(screen.getByTestId("type-0").textContent).toBe("message.created");
    expect(screen.getByTestId("type-1").textContent).toBe("message.created");
  });

  it("clears events when the session changes", () => {
    const { rerender } = render(
      <WebSocketProvider sessionId="sess-1">
        <EventConsumer />
      </WebSocketProvider>,
    );

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateOpen());
    act(() => {
      ws.simulateMessage(JSON.stringify(makeEvent({ id: "e1" })));
    });

    expect(screen.getByTestId("count").textContent).toBe("1");

    rerender(
      <WebSocketProvider sessionId="sess-2">
        <EventConsumer />
      </WebSocketProvider>,
    );

    expect(screen.getByTestId("count").textContent).toBe("0");
  });
});
