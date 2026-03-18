import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
} from "react";
import type { ReactNode } from "react";
import { WebSocketClient } from "@/api/websocket.ts";
import type {
  SessionEvent,
  ConnectionState,
  EventCallback,
} from "@/api/websocket.ts";
import { fetchEvents } from "@/api/events.ts";

interface WebSocketContextValue {
  connectionState: ConnectionState;
  events: SessionEvent[];
  onEvent: (callback: EventCallback) => void;
  removeListener: (callback: EventCallback) => void;
  injectEvents: (events: SessionEvent[]) => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

interface WebSocketProviderProps {
  sessionId: string | null;
  children: ReactNode;
}

/**
 * Merge historical events with live WebSocket events.
 * Deduplicates by event `id` and preserves chronological order
 * (historical first, then live).
 */
function mergeEvents(
  historical: SessionEvent[],
  live: SessionEvent[],
): SessionEvent[] {
  const seen = new Set<string>();
  const merged: SessionEvent[] = [];

  for (const e of historical) {
    if (!seen.has(e.id)) {
      seen.add(e.id);
      merged.push(e);
    }
  }

  for (const e of live) {
    if (!seen.has(e.id)) {
      seen.add(e.id);
      merged.push(e);
    }
  }

  return merged;
}

export function WebSocketProvider({
  sessionId,
  children,
}: WebSocketProviderProps) {
  const clientRef = useRef<WebSocketClient | null>(null);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");
  const [historicalEvents, setHistoricalEvents] = useState<SessionEvent[]>([]);
  const [liveEvents, setLiveEvents] = useState<SessionEvent[]>([]);

  useEffect(() => {
    if (!clientRef.current) {
      clientRef.current = new WebSocketClient();
    }
    const client = clientRef.current;
    let cancelled = false;

    const handleEvent: EventCallback = (event) => {
      setLiveEvents((prev) => [...prev, event]);
    };

    const handleState = (state: ConnectionState) => {
      setConnectionState(state);
    };

    client.onEvent(handleEvent);
    client.onStateChange(handleState);

    if (sessionId) {
      // Reset both event lists for the new session
      setLiveEvents([]);
      setHistoricalEvents([]);
      client.connect(sessionId);

      // Load historical events from the server
      fetchEvents(sessionId)
        .then((events) => {
          if (!cancelled) {
            setHistoricalEvents(events as SessionEvent[]);
          }
        })
        .catch((err) => {
          if (!cancelled) {
            console.warn("Failed to fetch session history:", err);
          }
        });
    } else {
      client.disconnect();
    }

    return () => {
      cancelled = true;
      client.removeListener(handleEvent);
      client.removeStateListener(handleState);
      client.disconnect();
    };
  }, [sessionId]);

  const events = useMemo(
    () => mergeEvents(historicalEvents, liveEvents),
    [historicalEvents, liveEvents],
  );

  const onEvent = useCallback((callback: EventCallback) => {
    clientRef.current?.onEvent(callback);
  }, []);

  const removeListener = useCallback((callback: EventCallback) => {
    clientRef.current?.removeListener(callback);
  }, []);

  const injectEvents = useCallback((newEvents: SessionEvent[]) => {
    setLiveEvents((prev) => [...prev, ...newEvents]);
  }, []);

  const value: WebSocketContextValue = {
    connectionState,
    events,
    onEvent,
    removeListener,
    injectEvents,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket(): WebSocketContextValue {
  const context = useContext(WebSocketContext);
  if (context === null) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return context;
}

/** Like useWebSocket but returns null when outside a WebSocketProvider. */
export function useWebSocketSafe(): WebSocketContextValue | null {
  return useContext(WebSocketContext);
}
