import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { WebSocketClient } from "@/api/websocket.ts";
import type { SessionEvent, EventCallback } from "@/api/websocket.ts";

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

  simulateError(): void {
    this.onerror?.();
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

describe("WebSocketClient", () => {
  let client: WebSocketClient;

  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.useFakeTimers();
    client = new WebSocketClient();
  });

  afterEach(() => {
    client.disconnect();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("connect(sessionId) opens a WebSocket to the correct URL", () => {
    client.connect("abc-123");

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe(
      "ws://localhost:7433/api/sessions/abc-123/ws",
    );
  });

  it("onEvent(callback) registers a listener that receives parsed events", () => {
    const callback = vi.fn();
    client.onEvent(callback);
    client.connect("sess-1");

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    const event = makeEvent();
    ws.simulateMessage(JSON.stringify(event));

    expect(callback).toHaveBeenCalledWith(event);
  });

  it("removeListener(callback) unregisters the listener", () => {
    const callback = vi.fn();
    client.onEvent(callback);
    client.connect("sess-1");

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    client.removeListener(callback);

    ws.simulateMessage(JSON.stringify(makeEvent()));
    expect(callback).not.toHaveBeenCalled();
  });

  it("disconnect() closes the WebSocket and stops reconnection", () => {
    client.connect("sess-1");
    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    client.disconnect();

    expect(ws.close).toHaveBeenCalled();
    expect(client.getState()).toBe("disconnected");
  });

  it("auto-reconnects with exponential backoff on unexpected close", () => {
    client.connect("sess-1");
    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    // Simulate unexpected close (not from disconnect)
    ws.simulateClose();
    expect(client.getState()).toBe("reconnecting");

    // After 1s, reconnect attempt
    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(2);

    // Second close -> next delay is 2s
    MockWebSocket.instances[1].simulateClose();
    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(2); // not yet
    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(3);

    // Third close -> next delay is 4s
    MockWebSocket.instances[2].simulateClose();
    vi.advanceTimersByTime(3000);
    expect(MockWebSocket.instances).toHaveLength(3); // not yet
    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(4);
  });

  it("backoff delay is capped at 30s", () => {
    client.connect("sess-1");

    // Simulate many failures to reach the cap
    for (let i = 0; i < 10; i++) {
      const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      ws.simulateClose();
      vi.advanceTimersByTime(30000);
    }

    const beforeCount = MockWebSocket.instances.length;
    const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    ws.simulateClose();

    // Should not reconnect before 30s
    vi.advanceTimersByTime(29999);
    expect(MockWebSocket.instances).toHaveLength(beforeCount);

    // Should reconnect at 30s
    vi.advanceTimersByTime(1);
    expect(MockWebSocket.instances).toHaveLength(beforeCount + 1);
  });

  it("resets backoff delay on successful reconnect", () => {
    client.connect("sess-1");
    MockWebSocket.instances[0].simulateOpen();

    // Close and wait for reconnect
    MockWebSocket.instances[0].simulateClose();
    vi.advanceTimersByTime(1000);
    // Now successfully reconnect
    MockWebSocket.instances[1].simulateOpen();

    // Close again -- delay should be back to 1s (not 2s)
    MockWebSocket.instances[1].simulateClose();
    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(3);
  });

  it("malformed messages trigger console.warn and do not call listeners", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const callback = vi.fn();
    client.onEvent(callback);
    client.connect("sess-1");

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();
    ws.simulateMessage("not valid json{{{");

    expect(warnSpy).toHaveBeenCalledWith(
      "WebSocket received malformed message:",
      "not valid json{{{",
    );
    expect(callback).not.toHaveBeenCalled();
  });

  it("calling connect() while already connected closes the previous connection", () => {
    client.connect("sess-1");
    const ws1 = MockWebSocket.instances[0];
    ws1.simulateOpen();

    client.connect("sess-2");

    expect(ws1.close).toHaveBeenCalled();
    expect(MockWebSocket.instances).toHaveLength(2);
    expect(MockWebSocket.instances[1].url).toBe(
      "ws://localhost:7433/api/sessions/sess-2/ws",
    );
  });

  it("exposes connection state changes via onStateChange", () => {
    const states: string[] = [];
    client.onStateChange((s) => states.push(s));

    client.connect("sess-1");
    expect(states).toEqual(["connecting"]);

    MockWebSocket.instances[0].simulateOpen();
    expect(states).toEqual(["connecting", "connected"]);

    client.disconnect();
    expect(states).toEqual(["connecting", "connected", "disconnected"]);
  });

  it("multiple event listeners all receive events", () => {
    const cb1: EventCallback = vi.fn();
    const cb2: EventCallback = vi.fn();
    client.onEvent(cb1);
    client.onEvent(cb2);
    client.connect("sess-1");

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    const event = makeEvent();
    ws.simulateMessage(JSON.stringify(event));

    expect(cb1).toHaveBeenCalledWith(event);
    expect(cb2).toHaveBeenCalledWith(event);
  });
});
