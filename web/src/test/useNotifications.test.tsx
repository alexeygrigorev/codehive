import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { WebSocketProvider } from "@/context/WebSocketContext.tsx";
import { useNotifications } from "@/hooks/useNotifications.ts";
import type { SessionEvent } from "@/api/websocket.ts";

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

function NotificationConsumer() {
  const { pendingQuestions, pendingApprovals } = useNotifications();
  return (
    <div>
      <span data-testid="questions">{pendingQuestions}</span>
      <span data-testid="approvals">{pendingApprovals}</span>
    </div>
  );
}

describe("useNotifications", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns zeros when no relevant events exist", () => {
    render(
      <WebSocketProvider sessionId="sess-1">
        <NotificationConsumer />
      </WebSocketProvider>,
    );

    expect(screen.getByTestId("questions").textContent).toBe("0");
    expect(screen.getByTestId("approvals").textContent).toBe("0");
  });

  it("increments pendingApprovals for each approval.required event", () => {
    render(
      <WebSocketProvider sessionId="sess-1">
        <NotificationConsumer />
      </WebSocketProvider>,
    );

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateOpen());

    act(() => {
      ws.simulateMessage(
        JSON.stringify(makeEvent({ id: "e1", type: "approval.required" })),
      );
    });
    act(() => {
      ws.simulateMessage(
        JSON.stringify(makeEvent({ id: "e2", type: "approval.required" })),
      );
    });

    expect(screen.getByTestId("approvals").textContent).toBe("2");
    expect(screen.getByTestId("questions").textContent).toBe("0");
  });

  it("increments pendingQuestions for session.waiting with reason pending_question", () => {
    render(
      <WebSocketProvider sessionId="sess-1">
        <NotificationConsumer />
      </WebSocketProvider>,
    );

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateOpen());

    act(() => {
      ws.simulateMessage(
        JSON.stringify(
          makeEvent({
            id: "e1",
            type: "session.waiting",
            data: { reason: "pending_question" },
          }),
        ),
      );
    });
    // This one should NOT count (different reason)
    act(() => {
      ws.simulateMessage(
        JSON.stringify(
          makeEvent({
            id: "e2",
            type: "session.waiting",
            data: { reason: "other" },
          }),
        ),
      );
    });

    expect(screen.getByTestId("questions").textContent).toBe("1");
    expect(screen.getByTestId("approvals").textContent).toBe("0");
  });

  it("does not count unrelated event types", () => {
    render(
      <WebSocketProvider sessionId="sess-1">
        <NotificationConsumer />
      </WebSocketProvider>,
    );

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateOpen());

    act(() => {
      ws.simulateMessage(
        JSON.stringify(makeEvent({ id: "e1", type: "message.created" })),
      );
    });
    act(() => {
      ws.simulateMessage(
        JSON.stringify(makeEvent({ id: "e2", type: "task.completed" })),
      );
    });

    expect(screen.getByTestId("questions").textContent).toBe("0");
    expect(screen.getByTestId("approvals").textContent).toBe("0");
  });
});
