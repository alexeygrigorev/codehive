import AsyncStorage from "@react-native-async-storage/async-storage";
import { SessionWebSocket } from "../src/api/ws";
import { STORAGE_KEYS } from "../src/api/client";

// Mock WebSocket
class MockWebSocket {
  url: string;
  onmessage: ((event: any) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = jest.fn();

  constructor(url: string) {
    this.url = url;
  }
}

(global as any).WebSocket = MockWebSocket;

beforeEach(async () => {
  await AsyncStorage.clear();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

describe("api/ws - SessionWebSocket", () => {
  it("constructs correct WebSocket URL using default base", async () => {
    const ws = new SessionWebSocket("session-123");
    await ws.connect();

    // Access the internal WebSocket to check URL
    const internal = (ws as any).ws as MockWebSocket;
    expect(internal.url).toBe("ws://10.0.2.2:7433/api/sessions/session-123/ws");

    ws.disconnect();
  });

  it("constructs correct WebSocket URL using stored base URL", async () => {
    await AsyncStorage.setItem(STORAGE_KEYS.BASE_URL, "http://myserver.com:9000");

    const ws = new SessionWebSocket("abc");
    await ws.connect();

    const internal = (ws as any).ws as MockWebSocket;
    expect(internal.url).toBe("ws://myserver.com:9000/api/sessions/abc/ws");

    ws.disconnect();
  });

  it("dispatches parsed JSON events to listeners", async () => {
    const ws = new SessionWebSocket("s1");
    const handler = jest.fn();
    ws.addListener(handler);
    await ws.connect();

    const internal = (ws as any).ws as MockWebSocket;
    internal.onmessage!({ data: JSON.stringify({ type: "message.created" }) });

    expect(handler).toHaveBeenCalledWith({ type: "message.created" });

    ws.disconnect();
  });

  it("schedules reconnect on connection close", async () => {
    const ws = new SessionWebSocket("s1");
    await ws.connect();

    const internal = (ws as any).ws as MockWebSocket;
    internal.onclose!();

    // There should be a reconnect timer scheduled
    expect(ws._getReconnectDelay()).toBe(1000);

    ws.disconnect();
  });

  it("uses exponential backoff for reconnect delays", async () => {
    const ws = new SessionWebSocket("s1");
    await ws.connect();

    // Simulate multiple disconnections
    let internal = (ws as any).ws as MockWebSocket;
    internal.onclose!();

    // After first close, delay should double from initial 1000 to 2000
    jest.advanceTimersByTime(1000);
    // Wait for async connect
    await Promise.resolve();

    expect(ws._getReconnectDelay()).toBe(2000);

    ws.disconnect();
  });

  it("removeListener stops receiving events", async () => {
    const ws = new SessionWebSocket("s1");
    const handler = jest.fn();
    ws.addListener(handler);
    await ws.connect();

    ws.removeListener(handler);

    const internal = (ws as any).ws as MockWebSocket;
    internal.onmessage!({ data: JSON.stringify({ type: "test" }) });

    expect(handler).not.toHaveBeenCalled();

    ws.disconnect();
  });

  it("disconnect prevents reconnection", async () => {
    const ws = new SessionWebSocket("s1");
    await ws.connect();

    ws.disconnect();

    // After disconnect, shouldReconnect should be false
    expect((ws as any).shouldReconnect).toBe(false);
    expect((ws as any).ws).toBeNull();
  });
});
