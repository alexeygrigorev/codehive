import AsyncStorage from "@react-native-async-storage/async-storage";
import { STORAGE_KEYS, DEFAULT_BASE_URL } from "./client";

export type EventHandler = (event: unknown) => void;

export class SessionWebSocket {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private shouldReconnect = true;
  private listeners: Set<EventHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
  }

  addListener(handler: EventHandler): void {
    this.listeners.add(handler);
  }

  removeListener(handler: EventHandler): void {
    this.listeners.delete(handler);
  }

  async connect(): Promise<void> {
    const storedUrl = await AsyncStorage.getItem(STORAGE_KEYS.BASE_URL);
    const base = (storedUrl ?? DEFAULT_BASE_URL).replace(/^http/, "ws");
    const url = `${base}/api/sessions/${this.sessionId}/ws`;

    this.ws = new WebSocket(url);

    this.ws.onmessage = (event: WebSocketMessageEvent) => {
      try {
        const parsed = JSON.parse(event.data);
        this.listeners.forEach((handler) => handler(parsed));
      } catch {
        // ignore non-JSON messages
      }
    };

    this.ws.onclose = () => {
      if (this.shouldReconnect) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // onclose will fire after onerror, triggering reconnect
    };
  }

  private scheduleReconnect(): void {
    this.reconnectTimer = setTimeout(() => {
      this.reconnectDelay = Math.min(
        this.reconnectDelay * 2,
        this.maxReconnectDelay
      );
      this.connect();
    }, this.reconnectDelay);
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /** Visible for testing */
  _getReconnectDelay(): number {
    return this.reconnectDelay;
  }
}
