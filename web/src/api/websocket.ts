import { apiClient } from "@/api/client.ts";

export type ConnectionState =
  | "connecting"
  | "connected"
  | "disconnected"
  | "reconnecting";

export interface SessionEvent {
  id: string;
  session_id: string;
  type: string;
  data: Record<string, unknown>;
  created_at: string;
}

export type EventCallback = (event: SessionEvent) => void;
export type StateCallback = (state: ConnectionState) => void;

function httpToWs(url: string): string {
  return url.replace(/^http(s?):/i, "ws$1:");
}

const INITIAL_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

/**
 * Normalize a raw WebSocket message into a proper SessionEvent.
 *
 * The backend EventBus publishes events with the full SessionEvent shape
 * (`id`, `session_id`, `type`, `data`, `created_at`). However, some code
 * paths (e.g. the POST /messages HTTP response) may produce flat events
 * without a `data` wrapper. This function ensures a consistent shape.
 */
export function normalizeEvent(raw: Record<string, unknown>): SessionEvent {
  // Already has a nested `data` object -- standard SessionEvent shape
  if (
    raw.data !== null &&
    raw.data !== undefined &&
    typeof raw.data === "object" &&
    !Array.isArray(raw.data)
  ) {
    return raw as unknown as SessionEvent;
  }

  // Flat event: extract known top-level fields, put the rest into `data`
  const { id, session_id, type, created_at, ...rest } = raw;
  return {
    id: (id as string) ?? crypto.randomUUID(),
    session_id: (session_id as string) ?? "",
    type: (type as string) ?? "unknown",
    data: rest as Record<string, unknown>,
    created_at: (created_at as string) ?? new Date().toISOString(),
  };
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private eventListeners: Set<EventCallback> = new Set();
  private stateListeners: Set<StateCallback> = new Set();
  private state: ConnectionState = "disconnected";
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay: number = INITIAL_DELAY_MS;
  private sessionId: string | null = null;
  private shouldReconnect: boolean = false;

  connect(sessionId: string): void {
    if (this.ws) {
      this.shouldReconnect = false;
      const ws = this.ws;
      this.ws = null;
      ws.onclose = null;
      ws.onmessage = null;
      ws.onopen = null;
      ws.onerror = null;
      ws.close();
    }
    this.clearReconnectTimer();

    this.sessionId = sessionId;
    this.shouldReconnect = true;
    this.reconnectDelay = INITIAL_DELAY_MS;
    this.openConnection();
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this.sessionId = null;
    this.clearReconnectTimer();
    if (this.ws) {
      const ws = this.ws;
      this.ws = null;
      ws.onclose = null;
      ws.onmessage = null;
      ws.onopen = null;
      ws.onerror = null;
      ws.close();
    }
    this.setState("disconnected");
  }

  onEvent(callback: EventCallback): void {
    this.eventListeners.add(callback);
  }

  removeListener(callback: EventCallback): void {
    this.eventListeners.delete(callback);
  }

  onStateChange(callback: StateCallback): void {
    this.stateListeners.add(callback);
  }

  removeStateListener(callback: StateCallback): void {
    this.stateListeners.delete(callback);
  }

  getState(): ConnectionState {
    return this.state;
  }

  private openConnection(): void {
    const wsBase = httpToWs(apiClient.baseURL);
    const url = `${wsBase}/api/sessions/${this.sessionId}/ws`;

    this.setState("connecting");

    const ws = new WebSocket(url);

    ws.onopen = () => {
      this.reconnectDelay = INITIAL_DELAY_MS;
      this.setState("connected");
    };

    ws.onmessage = (event: MessageEvent) => {
      let raw: Record<string, unknown>;
      try {
        raw = JSON.parse(event.data as string) as Record<string, unknown>;
      } catch {
        console.warn("WebSocket received malformed message:", event.data);
        return;
      }

      if (import.meta.env.DEV) {
        console.debug("[WS raw]", raw);
      }

      const parsed = normalizeEvent(raw);
      for (const listener of this.eventListeners) {
        listener(parsed);
      }
    };

    ws.onclose = () => {
      this.ws = null;
      if (this.shouldReconnect) {
        this.scheduleReconnect();
      } else {
        this.setState("disconnected");
      }
    };

    ws.onerror = () => {
      // onclose will fire after onerror, so reconnect is handled there
    };

    this.ws = ws;
  }

  private scheduleReconnect(): void {
    this.setState("reconnecting");
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.shouldReconnect && this.sessionId) {
        this.openConnection();
      }
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, MAX_DELAY_MS);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private setState(newState: ConnectionState): void {
    this.state = newState;
    for (const listener of this.stateListeners) {
      listener(newState);
    }
  }
}
